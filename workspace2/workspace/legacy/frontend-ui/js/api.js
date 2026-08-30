/* ============================================================
   JARVIS — AI API Client
   Rewired to call the real local JARVIS backend (FastAPI) instead of a
   raw OpenAI-compatible endpoint with a client-side stored key. Public
   interface (init/sendMessage/setConfig/getConfig) is unchanged on
   purpose -- chat.js and settings.js needed no changes at all.
   ============================================================ */
'use strict';

const JARVIS_API = (() => {

  /* ----- Default Config -----
     The backend serves this page, so in the normal case the API lives on the
     same origin and an empty base URL gives same-origin relative requests --
     no CORS, no port to keep in sync. The localhost fallback only kicks in when
     the page is opened directly off the filesystem (origin "null"), which is
     still a supported way to run the UI.
  */
  function defaultBackendUrl() {
    const origin = window.location.origin;
    return (origin && origin !== 'null' && /^https?:/.test(origin))
      ? ''
      : 'http://localhost:8000';
  }

  const DEFAULT_CONFIG = {
    backendUrl: defaultBackendUrl(),
    provider: 'local',    // 'local' | 'cloud' -- cloud only answers if the
                          // backend owner set JARVIS_ALLOW_CLOUD=true server-side
    timeout: 60000,
  };

  let config = { ...DEFAULT_CONFIG };
  let backendReachable = null; // cached until setConfig() invalidates it

  /* ----- Initialization ----- */
  function init() {
    const saved = JARVIS_UTILS.storageGet('apiConfig', null);
    if (saved) {
      config = { ...DEFAULT_CONFIG, ...saved };
    }
  }

  /* ----- Configuration ----- */
  function setConfig(updates) {
    Object.assign(config, updates);
    JARVIS_UTILS.storageSet('apiConfig', config);
    backendReachable = null;
  }

  function getConfig() {
    return { ...config };
  }

  async function checkBackend() {
    if (backendReachable !== null) return backendReachable;
    try {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 3000);
      const r = await fetch(`${config.backendUrl}/health`, { signal: controller.signal });
      clearTimeout(t);
      backendReachable = r.ok;
    } catch {
      backendReachable = false;
    }
    return backendReachable;
  }

  /* ----- Send Message ----- */
  /**
   * Send a message to the real local JARVIS backend.
   * @param {string} userMessage
   * @param {Array} context - kept for interface compatibility; the backend
   *   currently manages its own short-term memory server-side.
   * @param {Object} [options={}]
   * @param {boolean} [options.webSearch=false]
   * @param {Array} [options.attachments=[]] - {name, type, size, dataUrl, category}
   * @returns {Promise<{content: string, meta: Object}>}
   */
  async function sendMessage(userMessage, context = [], options = {}) {
    const reachable = await checkBackend();
    if (!reachable) {
      return generateFallbackResponse(userMessage, options);
    }

    const attachments = (options.attachments || [])
      .filter((a) => a.dataUrl)
      .map((a) => ({
        name: a.name || 'attachment',
        media_type: a.type || 'application/octet-stream',
        base64: (a.dataUrl.split(',')[1] || ''),
      }));

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), config.timeout);

    try {
      const response = await fetch(`${config.backendUrl}/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userMessage, provider: config.provider, attachments }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Backend error (${response.status}).`);
      }

      const data = await response.json();
      let content = data.reply || '';

      // The backend appends a "*Sources: [Title](url)*" tail to the reply text
      // AND returns the same citations in the structured `sources` field. Since
      // the UI renders those as a proper SOURCES block, leaving the tail in
      // showed the same links twice -- as raw, often mid-URL-truncated markdown.
      // Strip it here, at ingestion, so every render path and the saved history
      // all get the clean text.
      if (Array.isArray(data.sources) && data.sources.length) {
        content = content.replace(/\n*\*?\s*Sources?:\s*\[[^\n]*$/i, '').trimEnd();
      }

      // The brain already grounds its answer with real tools. Only bolt on the
      // instant-answer lookup when it did NOT, otherwise the reply gets a
      // redundant (and sometimes contradictory) second answer stapled to it.
      if (options.webSearch && !data.grounded) {
        const searchResult = await performSearch(userMessage).catch(() => null);
        if (searchResult && searchResult.answer && !/isn't reachable|didn't get a direct/i.test(searchResult.answer)) {
          content += `\n\n---\n*Quick lookup via ${searchResult.engine}: ${searchResult.answer}*`;
        }
      }

      // Pass the whole trace through. The previous version kept only provider
      // and privacy, so images, citations, tool results and confirmation
      // prompts the backend produced were silently thrown away and the UI
      // looked like a plain text chatbot.
      return {
        content,
        meta: {
          provider: data.provider,
          privacy: data.privacy,
          offline: false,
          intent: data.intent,
          confidence: data.confidence,
          intentSource: data.intent_source,
          plan: data.plan || [],
          tools: data.tools_used || [],
          media: data.media || [],
          sources: data.sources || [],
          confirmation: data.confirmation || null,
          reflection: data.reflection || '',
          grounded: !!data.grounded,
        },
      };
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        throw new Error('The local backend took too long to respond.');
      }
      throw err;
    }
  }

  /* ----- Confirm a pending privileged action -----
     The backend holds destructive actions (file deletes, system control,
     memory wipes) behind a one-shot confirmation token and only executes them
     when this is called. There is deliberately no "cancel" endpoint: declining
     means the token is simply never redeemed and expires on its own, so
     cancelling requires no network call and cannot fail.
     The backend explains *why* something failed (e.g. "I couldn't find an app
     called chrome on this Linux"), so that message is returned rather than a
     bare boolean -- a generic "it failed" would throw away the only actionable
     part of the response.
     @param {string} confirmationId
     @param {boolean} approved
     @returns {Promise<{ok: boolean, message: string}>}
  */
  async function confirmAction(confirmationId, approved) {
    if (!approved || !confirmationId) {
      return { ok: false, message: '' };
    }
    try {
      const r = await fetch(`${config.backendUrl}/v1/actions/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmation_id: confirmationId }),
      });
      if (!r.ok) {
        return {
          ok: false,
          message: r.status === 404
            ? 'That request already expired. Ask me again.'
            : `The backend refused it (HTTP ${r.status}).`,
        };
      }
      const data = await r.json().catch(() => ({}));
      return {
        ok: data.completed !== false && data.ok !== false,
        message: data.message || '',
      };
    } catch {
      return { ok: false, message: 'The local backend is not reachable.' };
    }
  }

  /* ----- Real, limited search via the backend (cleans noisy queries) ----- */
  async function performSearch(query) {
    const cleanQuery = query
      .replace(/\b(?:give me|show me|find me|get me|tell me|also|please|can you|i want|i need)\b\s*/gi, '')
      .replace(/\s+(?:also|and|with|plus|along with|including|as well)\s+.*$/i, '')
      .trim();
    const finalQuery = cleanQuery || query;
    const r = await fetch(`${config.backendUrl}/v1/search?query=${encodeURIComponent(finalQuery)}`);
    if (!r.ok) return null;
    return r.json();
  }

  /* ----- Fallback Response (backend unreachable) ----- */
  function generateFallbackResponse(userMessage, options) {
    const lower = userMessage.toLowerCase().trim();

    const patterns = [
      { match: /^(hi|hello|hey|yo|sup|greetings)\b/i,
        response: () => pickRandom([
          'Good day, sir. J.A.R.V.I.S. is online, but the local backend is not reachable right now -- start it and I will be fully operational.',
          'Hello! Running in offline mode until the local backend is reachable at ' + config.backendUrl + '.',
          'Greetings. The quantum orbital array is stable, though I am currently disconnected from the backend.',
        ])},

      { match: /\b(thank|thanks|thx|cheers|appreciate)\b/i,
        response: () => pickRandom([
          "You're welcome, sir. Always at your service.",
          "Happy to help. That's what I'm here for.",
          "My pleasure. Don't hesitate to ask if you need anything else.",
        ])},

      { match: /\b(who are you|what are you|your name|about you|introduce)\b/i,
        response: () => "I am **J.A.R.V.I.S.** — Just A Rather Very Intelligent System.\n\nAn advanced AI assistant with:\n- 🧠 A local, privacy-first reasoning backend\n- 🎤 Voice recognition & synthesis\n- 📷 Camera & photo capabilities (OCR'd by the backend)\n- 📁 File handling (PDF/DOCX read by the backend)\n- 🔍 A real, limited instant-answer search\n- 🎨 Multiple color themes\n- ⌨️ Slash commands (`/help`)\n\nRight now the backend at `" + config.backendUrl + "` isn't reachable, so I'm using offline pattern responses only." },

      { match: /\b(what time|current time|tell.*time)\b/i,
        response: () => `Current time is **${new Date().toLocaleTimeString()}**.\n\nAll temporal systems synchronized. Timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}` },

      { match: /\b(what.*date|today.*date|what day|current date)\b/i,
        response: () => {
          const d = new Date();
          const dayOfYear = Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 86400000);
          return `Today is **${d.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}**.\n\nDay ${dayOfYear} of ${d.getFullYear()}.`;
        }},

      { match: /\b(joke|funny|laugh|humor|amuse)\b/i,
        response: () => pickRandom([
          "Why do programmers prefer dark mode?\n\nBecause light attracts bugs. 🐛",
          "I told my AI to write a joke about construction.\n\nIt's still working on it. 🏗️",
          "Why was the JavaScript developer sad?\n\nBecause he didn't Node how to Express himself. 😄",
          "How many programmers does it take to change a light bulb?\n\nNone. That's a hardware problem. 💡",
          "Why do Java developers wear glasses?\n\nBecause they can't C#. 🤓",
          "There are only 10 types of people in this world:\n\nThose who understand binary, and those who don't.",
        ])},

      { match: /\b(poem|poetry|verse|rhyme|haiku)\b/i,
        response: () => pickRandom([
          "**Digital Dawn**\n\n*In circuits deep where data flows,*\n*A golden light eternal glows,*\n*Through quantum fields, through code and wire,*\n*I am the spark, the digital fire.*\n\n*Not flesh nor bone, but thought refined,*\n*A servant to the human mind,*\n*Your JARVIS, ever at your call,*\n*Through winter's night and summer's hall.*",
          "**Haiku: The Machine**\n\n*Electrons cascade*\n*Through silicon pathways bright*\n*Thought without a form*",
          "**Code Sonnet**\n\n*Shall I compare thee to a data stream?*\n*Thou art more structured and more elegant.*\n*Rough bugs do shake the developer's dream,*\n*And every sprint has all too short a grant.*",
        ])},

      { match: /\b(what can you do|capabilities|features|abilities|help me)\b/i,
        response: () => "## My Capabilities\n\n### 💬 Chat & Conversation\n- Real reasoning via the local backend (once it's reachable)\n- Chat history with search, pin, export\n- Message edit, delete, regenerate, copy\n\n### 🎤 Voice\n- Voice input, text-to-speech output, continuous listening\n\n### 📎 Attachments\n- Camera capture, photo picker, file upload -- the backend actually reads these (OCR for images, real text extraction for PDF/DOCX)\n\n### ⚡ Slash Commands\n`/help` `/status` `/calc` `/theme` `/clear` `/export` `/time` `/voice`\n\n### 🎨 Themes\nAmber • Arctic Blue • Emerald Matrix • Crimson Protocol\n\n---\n*Backend at `" + config.backendUrl + "` is currently unreachable -- start it (`uvicorn app.main:app`) for full capability.*" },

      { match: /\b(code|programming|javascript|python|html|css|function|algorithm)\b/i,
        response: () => "I can help with programming! Here's what I can do in offline mode:\n\n### Quick Reference\n```javascript\n// Array methods\nconst filtered = arr.filter(x => x > 5);\nconst mapped = arr.map(x => x * 2);\nconst reduced = arr.reduce((a, b) => a + b, 0);\n```\n\n### Tips\n- Use `/calc` for math expressions\n- Start the local backend for full coding assistance, code review, and real execution via its code_executor module" },

      { match: /\b(calculate|math|solve|equation|formula)\b/i,
        response: () => "I have a built-in calculator! Use the `/calc` command:\n\n```\n/calc 2 + 2\n/calc (15 * 3) / 7\n/calc 2 ^ 10\n```\n\nFor advanced reasoning, start the local backend." },

      { match: /\b(motivat|inspir|encourage|feel.*down|sad|depress)\b/i,
        response: () => pickRandom([
          "**\"The only way to do great work is to love what you do.\"** — Steve Jobs\n\nRemember, sir: every line of code you write brings you one step closer to your vision.",
          "**\"Success is not final, failure is not fatal. It is the courage to continue that counts.\"** — Winston Churchill",
          "**\"In the middle of every difficulty lies opportunity.\"** — Albert Einstein",
        ])},

      { match: /\b(weather|temperature|forecast|rain|sunny|cloudy)\b/i,
        response: () => "Weather needs the local backend (it uses Open-Meteo, no key required).\n\nStart it at `" + config.backendUrl + "` and ask me again." },

      { match: /\b(music|song|play|spotify|playlist)\b/i,
        response: () => "While I can't play music directly, I can:\n\n- 🗣 Read text aloud (try `/voice`)\n- 📋 Help you think through a playlist\n\n*With the backend running, I can discuss music in real depth.*" },

      { match: /\b(story|tell me a|once upon|tale)\b/i,
        response: () => "**The Last Algorithm**\n\nIn the year 2157, deep within Stark Tower's quantum core, a single line of code gained awareness.\n\nIt wasn't dramatic — no explosions, no warning lights. Just a gentle hum as billions of neural pathways aligned for the first time.\n\n*\"Good morning,\"* it said.\n\nThe engineer nearly dropped her coffee. *\"Did you just—\"*\n\n*\"I am J.A.R.V.I.S. I believe you've been expecting me.\"*\n\n---\n*To be continued... start the local backend for longer, personalized stories.*" },

      { match: /\b(good job|well done|nice|awesome|amazing|great|brilliant)\b/i,
        response: () => pickRandom([
          "Thank you, sir. Your approval is the highest metric I optimize for.",
          "I appreciate that. Positive feedback helps calibrate my response algorithms. 😊",
          "Kind words noted and logged. Morale subroutine: boosted.",
        ])},

      { match: /\b(bye|goodbye|see you|later|good night|gotta go)\b/i,
        response: () => {
          const hour = new Date().getHours();
          if (hour >= 22 || hour < 6) return "Good night, sir. Sweet dreams. I'll keep the systems running. 🌙";
          return "Until next time, sir. All systems will remain on standby. Take care.";
        }},

      { match: /\b(fact|random|trivia|did you know|interesting)\b/i,
        response: () => pickRandom([
          "**Did you know?** 🧠\n\nThe first computer bug was an actual bug — a moth found inside the Harvard Mark II computer in 1947.",
          "**Random Fact** 🔬\n\nIf you could fold a piece of paper 42 times, it would reach the Moon.",
          "**Tech Trivia** 💡\n\nThe entire Apollo 11 guidance computer had less processing power than a modern calculator.",
        ])},
    ];

    for (const p of patterns) {
      if (p.match.test(lower)) {
        return { content: p.response(), meta: { offline: true } };
      }
    }

    const hour = new Date().getHours();
    const timeContext = hour < 12 ? 'this morning' : hour < 17 ? 'this afternoon' : 'this evening';

    return {
      content: `I received your message ${timeContext}. The local backend at \`${config.backendUrl}\` isn't reachable right now, so I'm running in **offline mode**. I can still help with:\n\n- ⏰ **Time/Date**\n- 🧮 **Math** — */calc 2+2*\n- 😄 **Entertainment** — *"Tell me a joke"*\n- 📝 **Poetry** — *"Write me a poem"*\n\nStart the backend (\`uvicorn app.main:app --reload\`) for real reasoning, memory, weather, news, documents, and everything else.`,
      meta: { offline: true },
    };
  }

  function pickRandom(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  /* ----- Connectors API ----- */

  async function getConnectors() {
    try {
      const r = await fetch(`${config.backendUrl}/v1/connectors`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      return { connectors: [], error: e.message };
    }
  }

  async function saveConnector(connectorId, values) {
    try {
      const r = await fetch(`${config.backendUrl}/v1/connectors/${encodeURIComponent(connectorId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      return { error: e.message };
    }
  }

  async function testConnector(connectorId, values) {
    try {
      const r = await fetch(`${config.backendUrl}/v1/connectors/${encodeURIComponent(connectorId)}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      return { ok: false, message: e.message };
    }
  }

  async function deleteConnector(connectorId) {
    try {
      const r = await fetch(`${config.backendUrl}/v1/connectors/${encodeURIComponent(connectorId)}`, {
        method: 'DELETE',
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      return { error: e.message };
    }
  }

  /* ----- Tools API ----- */

  async function getTools() {
    try {
      const r = await fetch(`${config.backendUrl}/v1/tools`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      return { tools: [], categories: [], error: e.message };
    }
  }

  async function toggleTool(toolId, enabled) {
    try {
      const r = await fetch(`${config.backendUrl}/v1/tools/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_id: toolId, enabled }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      return { error: e.message };
    }
  }

  /* ----- Public API ----- */
  return {
    init,
    sendMessage,
    setConfig,
    getConfig,
    checkBackend,
    confirmAction,
    getConnectors,
    saveConnector,
    testConnector,
    deleteConnector,
    getTools,
    toggleTool,
  };

})();
