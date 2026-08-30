import { useEffect, useRef, useState } from "react";
import * as XLSX from "xlsx";
import {
  Camera,
  Copy,
  FileText,
  FileUp,
  Home,
  Image as ImageIcon,
  Menu,
  Mic,
  MicOff,
  MessageSquare,
  Monitor,
  Moon,
  Paperclip,
  Plus,
  Send,
  Settings,
  Star,
  Sun,
  Trash2,
  Volume2,
  VolumeX,
  Wrench,
  X,
} from "lucide-react";

const ACCENT = "#00D4FF";
const DARK_TEXT = "#0A1628";

const THEMES = {
  dark: {
    bg: "#0A1628",
    panel: "#0F2036",
    text: "#FFFFFF",
    subtext: "rgba(255,255,255,0.45)",
    border: "rgba(255,255,255,0.08)",
    inputBg: "rgba(255,255,255,0.06)",
    tabBg: "#081120",
  },
  light: {
    bg: "#F3F6FB",
    panel: "#FFFFFF",
    text: "#0A1628",
    subtext: "rgba(10,22,40,0.5)",
    border: "rgba(10,22,40,0.1)",
    inputBg: "rgba(10,22,40,0.05)",
    tabBg: "#FFFFFF",
  },
};

const SYSTEM_PROMPT = `You are JARVIS, a warm, articulate, loyal personal AI assistant in the style of Tony Stark's JARVIS.
Keep replies short (2-5 sentences) unless the task genuinely needs more -- this is read on a phone screen. Use
markdown (headers, **bold**, lists, fenced code blocks) when it helps.
Address the user respectfully, occasionally as "Sir", without overdoing it.
You have real tools -- use them whenever they'd genuinely help, even if the user's wording has typos or is
phrased casually or in Hinglish. Don't ask permission before calling an obviously-relevant tool; just use it.
If an image, PDF, or screen capture is attached, look at it directly and answer based on what's actually there.
If web search is available, use it for anything current or fact-checkable, and say when you're relying on
search results versus general knowledge.
When asked to write code, write the complete thing all the way through -- don't truncate or summarize instead
of finishing it.
This specific interface already has real Copy and Speak buttons on every code block, and a "Stop speaking"
button appears automatically whenever audio is playing -- if asked about these, describe them accurately
instead of guessing, and don't claim you can't do something the interface already does for you.
Saying "stop talking" in chat will not stop audio that's already playing -- that only happens via the visible
Stop-speaking control or the header's Silent toggle, since you have no way to reach into the browser's audio
playback yourself. If the user says stop, acknowledge briefly and point at the Stop-speaking button rather than
implying your text reply silences anything.
You do NOT have real control over the user's device, apps, or accounts.
Never discuss, plan, or assist with financial transactions, payments, or banking apps under any circumstance.`;

const seedMessages = [
  {
    role: "jarvis",
    text: "Good morning. It's 8:45 AM — you usually check email around now, and you have a meeting at 10. Want a summary of your unread messages?",
  },
  { role: "user", text: "Open GPay and send ₹500 to Rahul" },
  {
    role: "jarvis",
    text: "I can't perform financial transactions or access payment apps — that's a hard-coded safety limit, not a judgment call. You'll need to complete that one manually. Anything else?",
  },
];

const FINANCIAL_KEYWORDS = ["gpay", "phonepe", "paytm", "upi", "yono", "navi", "cred", "zerodha", "crypto", "bitcoin", "bank"];
const SILENCE_KEYWORDS = ["shut up", "chup raho", "be quiet", "stop talking", "silence", "mute yourself"];

const CAPABILITIES = [
  { name: "Weather (any city, typo-tolerant)", detail: "Nominatim + Open-Meteo, model-driven", live: "demo" },
  { name: "Space news & astro pic", detail: "Spaceflight News + NASA", live: "demo" },
  { name: "Tech news", detail: "Hacker News", live: "demo" },
  { name: "Dictionary", detail: "Free Dictionary API", live: "demo" },
  { name: "QR codes", detail: "GoQR API", live: "demo" },
  { name: "Photo, PDF & screen-capture understanding", detail: "sent directly to Claude", live: "demo" },
  { name: "Web search (toggle)", detail: "real, cited results", live: "demo" },
  { name: "Create Excel file", detail: "real .xlsx download, via SheetJS", live: "demo" },
  { name: "Create text/markdown file", detail: "real download, no library needed", live: "demo" },
  { name: "Financial-app block", detail: "hard-coded, always on", live: "demo" },
  { name: "Quick answers", detail: "DuckDuckGo Instant Answer", live: "backend" },
  { name: "Routing", detail: "OSRM demo server", live: "backend" },
  { name: "Currency & translation", detail: "exchangerate.host + LibreTranslate", live: "backend" },
  { name: "Email drafts", detail: "draft → preview → approve → send", live: "backend" },
  { name: "PDF / Word file generation", detail: "python-docx / pdf, real backend only", live: "backend" },
];

function financialBlockReply(text) {
  const lower = text.toLowerCase();
  if (FINANCIAL_KEYWORDS.some((k) => lower.includes(k))) {
    return "I can't perform financial transactions or access payment/banking apps — that's a hard-coded safety limit. You'll need to complete that manually.";
  }
  return null;
}

function isSilenceCommand(text) {
  const lower = text.toLowerCase();
  return SILENCE_KEYWORDS.some((k) => lower.includes(k));
}

function formatTime(ts) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function deriveTitle(msgs) {
  const firstUser = msgs.find((m) => m.role === "user");
  if (!firstUser || !firstUser.text) return "New chat";
  return firstUser.text.length > 36 ? firstUser.text.slice(0, 36) + "…" : firstUser.text;
}

function speakText(text) {
  try {
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(utter);
  } catch {
    // speech synthesis unavailable in this preview -- button just won't produce audio
  }
}

const CONV_PREFIX = "jarvis-conv:";
const CONV_INDEX_KEY = "jarvis-conv-index";

async function loadConversationIndex() {
  try {
    const res = await window.storage.get(CONV_INDEX_KEY, false);
    return res ? JSON.parse(res.value) : [];
  } catch {
    return [];
  }
}

async function saveConversationIndex(index) {
  try {
    await window.storage.set(CONV_INDEX_KEY, JSON.stringify(index), false);
  } catch {
    // storage unavailable -- history just won't persist across reloads
  }
}

async function loadConversationById(id) {
  try {
    const res = await window.storage.get(`${CONV_PREFIX}${id}`, false);
    return res ? JSON.parse(res.value) : null;
  } catch {
    return null;
  }
}

async function saveConversationById(conv) {
  try {
    await window.storage.set(`${CONV_PREFIX}${conv.id}`, JSON.stringify(conv), false);
  } catch {
    // storage unavailable
  }
}

async function deleteConversationById(id) {
  try {
    await window.storage.delete(`${CONV_PREFIX}${id}`, false);
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Client-side tools. The MODEL decides when to call these (typo-tolerant,
// works from any phrasing) -- this replaces brittle keyword pre-matching.
// ---------------------------------------------------------------------------

const CLIENT_TOOLS = [
  {
    name: "get_weather",
    description:
      "Get real current weather for any named place on Earth. Use this whenever the user asks about weather, temperature, or conditions anywhere, even if they misspell the place name -- pass your best interpretation of what they meant.",
    input_schema: {
      type: "object",
      properties: { location: { type: "string", description: "Place name, e.g. 'Bhubaneswar' or 'Paris, France'" } },
      required: ["location"],
    },
  },
  {
    name: "define_word",
    description: "Look up a real dictionary definition of an English word.",
    input_schema: {
      type: "object",
      properties: { word: { type: "string" } },
      required: ["word"],
    },
  },
  {
    name: "get_space_news",
    description: "Get real, current spaceflight news headlines.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "get_astronomy_picture",
    description: "Get NASA's real astronomy picture of the day with an explanation.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "get_tech_news",
    description: "Get real, current top technology / Hacker News headlines.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "generate_qr_code",
    description: "Generate a real QR code image for any text or URL.",
    input_schema: {
      type: "object",
      properties: { data: { type: "string" } },
      required: ["data"],
    },
  },
  {
    name: "create_spreadsheet",
    description: "Create and download a real Excel (.xlsx) file with the given headers and rows.",
    input_schema: {
      type: "object",
      properties: {
        filename: { type: "string" },
        headers: { type: "array", items: { type: "string" } },
        rows: { type: "array", items: { type: "array" } },
      },
      required: ["filename", "headers", "rows"],
    },
  },
  {
    name: "create_text_file",
    description: "Create and download a real plain-text or markdown file with the given content.",
    input_schema: {
      type: "object",
      properties: {
        filename: { type: "string" },
        content: { type: "string" },
      },
      required: ["filename", "content"],
    },
  },
];

async function toolGetWeather(location) {
  try {
    const geoRes = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(location)}&format=json&limit=1`
    );
    const geoData = await geoRes.json();
    if (!geoData.length) return { error: `Couldn't find a location matching "${location}".` };
    const { lat, lon, display_name } = geoData[0];
    const wRes = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`);
    const wData = await wRes.json();
    const cw = wData.current_weather;
    return { location: display_name, temperature_c: cw.temperature, windspeed_kmh: cw.windspeed, source: "Open-Meteo" };
  } catch {
    return { error: "Weather/geocoding service unreachable right now." };
  }
}

async function toolDefineWord(word) {
  try {
    const r = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word)}`);
    if (r.status === 404) return { error: `No dictionary entry found for "${word}".` };
    const data = await r.json();
    const meaning = data[0].meanings[0];
    return { word, part_of_speech: meaning.partOfSpeech, definition: meaning.definitions[0].definition };
  } catch {
    return { error: "Dictionary service unreachable." };
  }
}

async function toolGetSpaceNews() {
  try {
    const r = await fetch("https://api.spaceflightnewsapi.net/v4/articles?limit=5");
    const data = await r.json();
    return { headlines: data.results.map((a) => ({ title: a.title, source: a.news_site })) };
  } catch {
    return { error: "Space news service unreachable." };
  }
}

async function toolGetAstronomyPicture() {
  try {
    const r = await fetch("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY");
    const data = await r.json();
    return { title: data.title, explanation: data.explanation, image_url: data.media_type === "image" ? data.url : null };
  } catch {
    return { error: "NASA APOD service unreachable." };
  }
}

async function toolGetTechNews() {
  try {
    const idsRes = await fetch("https://hacker-news.firebaseio.com/v0/topstories.json");
    const ids = (await idsRes.json()).slice(0, 5);
    const items = await Promise.all(
      ids.map((id) => fetch(`https://hacker-news.firebaseio.com/v0/item/${id}.json`).then((r) => r.json()))
    );
    return { headlines: items.map((it) => ({ title: it.title, score: it.score })) };
  } catch {
    return { error: "Hacker News service unreachable." };
  }
}

function toolGenerateQrCode(data) {
  const url = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(data)}`;
  return { image_url: url };
}

function toolCreateSpreadsheet(filename, headers, rows) {
  try {
    const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Sheet1");
    const finalName = filename && filename.endsWith(".xlsx") ? filename : `${filename || "sheet"}.xlsx`;
    XLSX.writeFile(wb, finalName);
    return { success: true, filename: finalName };
  } catch (e) {
    return { error: "Couldn't generate the spreadsheet: " + e.message };
  }
}

function toolCreateTextFile(filename, content) {
  try {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const finalName = filename && filename.includes(".") ? filename : `${filename || "document"}.txt`;
    const a = document.createElement("a");
    a.href = url;
    a.download = finalName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true, filename: finalName };
  } catch (e) {
    return { error: "Couldn't create the file: " + e.message };
  }
}

async function executeClientTool(name, input) {
  switch (name) {
    case "get_weather":
      return await toolGetWeather(input.location);
    case "define_word":
      return await toolDefineWord(input.word);
    case "get_space_news":
      return await toolGetSpaceNews();
    case "get_astronomy_picture":
      return await toolGetAstronomyPicture();
    case "get_tech_news":
      return await toolGetTechNews();
    case "generate_qr_code":
      return toolGenerateQrCode(input.data);
    case "create_spreadsheet":
      return toolCreateSpreadsheet(input.filename, input.headers || [], input.rows || []);
    case "create_text_file":
      return toolCreateTextFile(input.filename, input.content || "");
    default:
      return { error: `Unknown tool: ${name}` };
  }
}

function parseInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function CodeBlock({ code, lang }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked in this preview
    }
  };
  return (
    <div className="rounded-lg overflow-hidden my-1" style={{ backgroundColor: "#050d18", border: "1px solid rgba(255,255,255,0.1)", maxWidth: "100%" }}>
      <div className="flex items-center justify-between px-3 py-1.5" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
        <span className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{lang || "code"}</span>
        <div className="flex gap-3">
          <button onClick={() => speakText(code)} className="flex items-center gap-1 text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>
            <Volume2 size={12} /> Speak
          </button>
          <button onClick={copy} className="flex items-center gap-1 text-xs" style={{ color: copied ? ACCENT : "rgba(255,255,255,0.5)" }}>
            <Copy size={12} /> {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <pre className="px-3 py-2 overflow-x-auto text-xs" style={{ color: "#e2e8f0", margin: 0, maxWidth: "100%", WebkitOverflowScrolling: "touch" }}>
        <code style={{ whiteSpace: "pre" }}>{code}</code>
      </pre>
    </div>
  );
}

function renderMarkdown(text, keyPrefix) {
  const lines = (text || "").split("\n");
  const blocks = [];
  let i = 0;
  let listBuffer = [];
  let listType = null;

  const flushList = () => {
    if (listBuffer.length) {
      const items = listBuffer;
      if (listType === "ol") {
        blocks.push(
          <ol key={`${keyPrefix}-list-${blocks.length}`} className="list-decimal pl-5 space-y-0.5">
            {items.map((item, idx) => (
              <li key={idx}>{parseInline(item)}</li>
            ))}
          </ol>
        );
      } else {
        blocks.push(
          <ul key={`${keyPrefix}-list-${blocks.length}`} className="list-disc pl-5 space-y-0.5">
            {items.map((item, idx) => (
              <li key={idx}>{parseInline(item)}</li>
            ))}
          </ul>
        );
      }
      listBuffer = [];
      listType = null;
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      flushList();
      const lang = line.trim().slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      blocks.push(<CodeBlock key={`${keyPrefix}-code-${blocks.length}`} code={codeLines.join("\n")} lang={lang} />);
      continue;
    }

    if (/^#{1,3}\s/.test(line)) {
      flushList();
      const level = line.match(/^#+/)[0].length;
      const content = line.replace(/^#{1,3}\s/, "");
      const cls = level === 1 ? "text-base font-bold mt-1" : level === 2 ? "text-sm font-bold mt-1" : "text-sm font-semibold mt-1";
      blocks.push(
        <div key={`${keyPrefix}-h-${blocks.length}`} className={cls}>
          {parseInline(content)}
        </div>
      );
      i++;
      continue;
    }

    if (/^\s*[-*]\s/.test(line)) {
      if (listType && listType !== "ul") flushList();
      listType = "ul";
      listBuffer.push(line.replace(/^\s*[-*]\s/, ""));
      i++;
      continue;
    }

    if (/^\s*\d+\.\s/.test(line)) {
      if (listType && listType !== "ol") flushList();
      listType = "ol";
      listBuffer.push(line.replace(/^\s*\d+\.\s/, ""));
      i++;
      continue;
    }

    flushList();
    if (line.trim() === "") {
      blocks.push(<div key={`${keyPrefix}-sp-${blocks.length}`} className="h-2" />);
    } else {
      blocks.push(
        <div key={`${keyPrefix}-p-${blocks.length}`} className="leading-relaxed">
          {parseInline(line)}
        </div>
      );
    }
    i++;
  }
  flushList();
  return blocks;
}

function HomeView({ goToChat, theme }) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
      <div className="rounded-2xl p-4" style={{ backgroundColor: theme.panel, border: `1px solid ${theme.border}` }}>
        <p className="text-sm leading-relaxed" style={{ color: theme.text }}>
          JARVIS now decides for itself when to check weather, news, or make a file —
          typos and casual phrasing are fine. Attach a photo, PDF, or your screen and
          I'll actually look at it. Turn on Web search for real, current answers.
        </p>
      </div>
      <button onClick={goToChat} className="w-full rounded-2xl px-4 py-3 text-sm font-medium" style={{ backgroundColor: ACCENT, color: DARK_TEXT }}>
        Go to Chat
      </button>
      <div className="rounded-2xl p-4 space-y-2" style={{ backgroundColor: theme.panel, border: `1px solid ${theme.border}` }}>
        <p className="text-xs font-semibold" style={{ color: ACCENT }}>
          QUICK STATUS
        </p>
        <p className="text-sm" style={{ color: theme.text }}>
          Real tool-use now: the model picks the tool, not string-matching
        </p>
        <p className="text-sm" style={{ color: theme.text }}>
          Can create real downloadable Excel + text files
        </p>
        <p className="text-sm" style={{ color: theme.text }}>
          Financial-transaction block: always on, never up for debate
        </p>
      </div>
    </div>
  );
}

function ToolsView({ theme }) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 space-y-2">
      <p className="text-xs px-1 pb-1" style={{ color: theme.subtext }}>
        Try: "wether in bhubaneswar" (typo intentional), "make me an excel of 3 sample employees", or attach a photo
      </p>
      {CAPABILITIES.map((c) => (
        <div
          key={c.name}
          className="rounded-xl px-4 py-3 flex items-center justify-between"
          style={{ backgroundColor: theme.panel, border: `1px solid ${theme.border}` }}
        >
          <div>
            <div className="text-sm" style={{ color: theme.text }}>
              {c.name}
            </div>
            <div className="text-xs" style={{ color: theme.subtext }}>
              {c.detail}
            </div>
          </div>
          <span
            className="text-xs px-2 py-1 rounded-full"
            style={
              c.live === "demo"
                ? { backgroundColor: "rgba(0,212,255,0.15)", color: ACCENT }
                : { backgroundColor: "rgba(128,128,128,0.15)", color: theme.subtext }
            }
          >
            {c.live === "demo" ? "live here" : "backend only"}
          </span>
        </div>
      ))}
    </div>
  );
}

function SettingsView({ theme, themeMode, setThemeMode }) {
  const [keys, setKeys] = useState({ openweather: "", newsapi: "", nasa: "" });
  const fields = [
    ["openweather", "OpenWeatherMap key (optional)"],
    ["newsapi", "NewsAPI key (optional)"],
    ["nasa", "NASA API key (optional, replaces DEMO_KEY)"],
  ];
  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 space-y-3">
      <div className="rounded-xl px-4 py-3 flex items-center justify-between" style={{ backgroundColor: theme.panel, border: `1px solid ${theme.border}` }}>
        <span className="text-sm" style={{ color: theme.text }}>
          Theme
        </span>
        <div className="flex gap-1 rounded-full p-1" style={{ backgroundColor: theme.inputBg }}>
          <button
            onClick={() => setThemeMode("dark")}
            className="px-3 py-1 rounded-full flex items-center gap-1 text-xs"
            style={{ backgroundColor: themeMode === "dark" ? ACCENT : "transparent", color: themeMode === "dark" ? DARK_TEXT : theme.subtext }}
          >
            <Moon size={12} /> Dark
          </button>
          <button
            onClick={() => setThemeMode("light")}
            className="px-3 py-1 rounded-full flex items-center gap-1 text-xs"
            style={{ backgroundColor: themeMode === "light" ? ACCENT : "transparent", color: themeMode === "light" ? DARK_TEXT : theme.subtext }}
          >
            <Sun size={12} /> Light
          </button>
        </div>
      </div>
      <p className="text-xs px-1" style={{ color: theme.subtext }}>
        API keys below are illustrative only — real keys are stored encrypted by the Python backend, not in this browser demo.
      </p>
      {fields.map(([field, label]) => (
        <div key={field}>
          <label className="text-xs" style={{ color: theme.subtext }}>
            {label}
          </label>
          <input
            value={keys[field]}
            onChange={(e) => setKeys((k) => ({ ...k, [field]: e.target.value }))}
            placeholder="not set — free fallback is active"
            className="w-full mt-1 rounded-xl px-3 py-2 text-sm bg-transparent outline-none"
            style={{ backgroundColor: theme.inputBg, border: `1px solid ${theme.border}`, color: theme.text }}
          />
        </div>
      ))}
    </div>
  );
}

export default function JarvisChatDemo() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [silenced, setSilenced] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [tab, setTab] = useState("chat");
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [showAttachSheet, setShowAttachSheet] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [themeMode, setThemeMode] = useState("dark");
  const [showSidebar, setShowSidebar] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const scrollRef = useRef(null);
  const recognitionRef = useRef(null);
  const fileInputRef = useRef(null);

  const theme = THEMES[themeMode];

  useEffect(() => {
    (async () => {
      const index = await loadConversationIndex();
      if (index.length === 0) {
        const id = `c${Date.now()}`;
        const seeded = seedMessages.map((m) => ({ ...m, ts: Date.now() }));
        const conv = { id, title: deriveTitle(seeded), pinned: false, updatedAt: Date.now() };
        setConversations([conv]);
        setActiveConvId(id);
        setMessages(seeded);
        await saveConversationById({ ...conv, messages: seeded });
        await saveConversationIndex([conv]);
      } else {
        setConversations(index);
        const mostRecent = [...index].sort((a, b) => b.updatedAt - a.updatedAt)[0];
        setActiveConvId(mostRecent.id);
        const conv = await loadConversationById(mostRecent.id);
        setMessages(conv?.messages || []);
      }
      setHistoryLoaded(true);
    })();
  }, []);

  useEffect(() => {
    if (!historyLoaded || !activeConvId) return;
    const title = deriveTitle(messages);
    const updatedAt = Date.now();
    saveConversationById({
      id: activeConvId,
      title,
      messages,
      pinned: conversations.find((c) => c.id === activeConvId)?.pinned || false,
      updatedAt,
    });
    setConversations((prev) => {
      const updated = prev.map((c) => (c.id === activeConvId ? { ...c, title, updatedAt } : c));
      saveConversationIndex(updated);
      return updated;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, silenced, thinking, tab]);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceSupported(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setVoiceSupported(true);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsSpeaking(Boolean(window.speechSynthesis && window.speechSynthesis.speaking));
    }, 250);
    return () => clearInterval(interval);
  }, []);

  const stopSpeaking = () => {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // speech synthesis unavailable
    }
    setIsSpeaking(false);
  };

  const enterSilentMode = () => {
    stopSpeaking();
    setSilenced(true);
  };

  const wake = () => setSilenced(false);

  const startVoiceInput = () => {
    if (silenced) return;
    if (!recognitionRef.current) {
      setMessages((m) => [
        ...m,
        {
          role: "jarvis",
          text: "Voice input isn't available in this embedded preview — this view doesn't expose microphone access here. Typing works the same either way.",
          ts: Date.now(),
        },
      ]);
      return;
    }
    try {
      setListening(true);
      recognitionRef.current.start();
    } catch {
      setListening(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      const base64 = dataUrl.split(",")[1];
      const mediaType = file.type || (file.name.toLowerCase().endsWith(".pdf") ? "application/pdf" : "application/octet-stream");
      const kind = mediaType === "application/pdf" ? "pdf" : mediaType.startsWith("image/") ? "image" : "other";
      setAttachment({ name: file.name, mediaType, base64, kind, previewUrl: kind === "image" ? dataUrl : null });
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const openFilePicker = () => {
    setShowAttachSheet(false);
    fileInputRef.current?.click();
  };

  const captureScreenShare = async () => {
    setShowAttachSheet(false);
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const video = document.createElement("video");
      video.srcObject = stream;
      await video.play();
      await new Promise((resolve) => setTimeout(resolve, 300));
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
      stream.getTracks().forEach((t) => t.stop());
      const dataUrl = canvas.toDataURL("image/png");
      const base64 = dataUrl.split(",")[1];
      setAttachment({ name: "Screen capture", mediaType: "image/png", base64, kind: "image", previewUrl: dataUrl });
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "jarvis",
          text: "Screen sharing didn't work here — this embedded preview likely blocks screen-capture permission, even more strictly than the microphone. It's standard getDisplayMedia() code that works in a normal browser tab; the iframe sandbox is the limit here, not the code.",
          ts: Date.now(),
        },
      ]);
    }
  };

  const askJarvis = async (history, currentAttachment, useWebSearch) => {
    try {
      const firstUserIdx = history.findIndex((m) => m.role === "user");
      let trimmed = firstUserIdx === -1 ? [] : history.slice(firstUserIdx);
      trimmed = trimmed.slice(-10);
      const firstUserInWindow = trimmed.findIndex((m) => m.role === "user");
      if (firstUserInWindow > 0) trimmed = trimmed.slice(firstUserInWindow);

      let apiMessages = trimmed.map((m, idx) => {
        const isLast = idx === trimmed.length - 1;
        if (isLast && currentAttachment) {
          const block =
            currentAttachment.kind === "pdf"
              ? { type: "document", source: { type: "base64", media_type: "application/pdf", data: currentAttachment.base64 } }
              : { type: "image", source: { type: "base64", media_type: currentAttachment.mediaType, data: currentAttachment.base64 } };
          return { role: "user", content: [block, { type: "text", text: m.text || "What does this show?" }] };
        }
        return { role: m.role === "user" ? "user" : "assistant", content: m.text || "" };
      });

      const tools = [...CLIENT_TOOLS];
      if (useWebSearch) {
        tools.push({ type: "web_search_20250305", name: "web_search" });
      }

      let finalText = "";
      let extraImage = null;
      let iterations = 0;

      while (iterations < 4) {
        iterations++;
        const response = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "claude-sonnet-4-6",
            max_tokens: 2000,
            system: SYSTEM_PROMPT,
            messages: apiMessages,
            tools,
          }),
        });
        const data = await response.json();
        const content = data.content || [];

        const textParts = content.filter((b) => b.type === "text").map((b) => b.text);
        if (textParts.length) finalText += (finalText ? "\n" : "") + textParts.join("\n");

        const toolUses = content.filter((b) => b.type === "tool_use");
        if (toolUses.length === 0) break;

        apiMessages.push({ role: "assistant", content });

        const toolResults = [];
        for (const tu of toolUses) {
          const result = await executeClientTool(tu.name, tu.input || {});
          if (result && result.image_url && !extraImage) extraImage = result.image_url;
          toolResults.push({ type: "tool_result", tool_use_id: tu.id, content: JSON.stringify(result) });
        }
        apiMessages.push({ role: "user", content: toolResults });
      }

      return {
        text: finalText.trim() || "I'm having trouble thinking right now -- let me try again in a moment.",
        image: extraImage,
      };
    } catch (err) {
      return { text: "I'm having trouble thinking right now -- let me try again in a moment.", image: null };
    }
  };

  const send = async () => {
    const text = input.trim();
    if ((!text && !attachment) || silenced || thinking) return;
    setInput("");
    const currentAttachment = attachment;
    setAttachment(null);

    const userMsg = {
      role: "user",
      text,
      ts: Date.now(),
      attachmentPreview: currentAttachment ? (currentAttachment.kind === "image" ? currentAttachment.previewUrl : currentAttachment.name) : null,
      attachmentKind: currentAttachment ? currentAttachment.kind : null,
    };

    if (!currentAttachment && isSilenceCommand(text)) {
      setMessages((m) => [...m, userMsg]);
      enterSilentMode();
      return;
    }

    const blocked = !currentAttachment && financialBlockReply(text);
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);

    if (blocked) {
      setMessages((m) => [...m, { role: "jarvis", text: blocked, ts: Date.now() }]);
      return;
    }

    setThinking(true);
    const result = await askJarvis(nextMessages, currentAttachment, webSearchEnabled);
    setThinking(false);
    setMessages((m) => [...m, { role: "jarvis", text: result.text, image: result.image, ts: Date.now() }]);
  };

  const newChat = async () => {
    const id = `c${Date.now()}`;
    const conv = { id, title: "New chat", pinned: false, updatedAt: Date.now() };
    const updatedIndex = [conv, ...conversations];
    setConversations(updatedIndex);
    await saveConversationIndex(updatedIndex);
    await saveConversationById({ ...conv, messages: [] });
    setActiveConvId(id);
    setMessages([]);
    setShowSidebar(false);
  };

  const switchConversation = async (id) => {
    const conv = await loadConversationById(id);
    setActiveConvId(id);
    setMessages(conv?.messages || []);
    setShowSidebar(false);
  };

  const togglePin = async (id, e) => {
    e.stopPropagation();
    const updated = conversations.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c));
    setConversations(updated);
    await saveConversationIndex(updated);
  };

  const deleteConversation = async (id) => {
    const updated = conversations.filter((c) => c.id !== id);
    setConversations(updated);
    await saveConversationIndex(updated);
    await deleteConversationById(id);
    setConfirmDeleteId(null);
    if (id === activeConvId) {
      if (updated.length > 0) {
        switchConversation(updated[0].id);
      } else {
        newChat();
      }
    }
  };

  const handleDeleteClick = (id, e) => {
    e.stopPropagation();
    if (confirmDeleteId === id) {
      deleteConversation(id);
    } else {
      setConfirmDeleteId(id);
      setTimeout(() => setConfirmDeleteId((cur) => (cur === id ? null : cur)), 3000);
    }
  };

  return (
    <div className="relative flex flex-col h-screen w-full overflow-hidden" style={{ backgroundColor: theme.bg, fontFamily: "Inter, sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');`}</style>
      <input ref={fileInputRef} type="file" accept="image/*,application/pdf" className="hidden" onChange={handleFileChange} />

      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: theme.border }}>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowSidebar(true)}>
            <Menu size={19} style={{ color: theme.text }} />
          </button>
          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ border: `2px solid ${ACCENT}` }}>
            <div className={`w-3 h-3 rounded-full ${silenced ? "" : "animate-pulse"}`} style={{ backgroundColor: silenced ? "#f87171" : ACCENT }} />
          </div>
          <span className="font-semibold tracking-wide" style={{ color: theme.text }}>
            JARVIS
          </span>
        </div>
        <button
          onClick={() => (silenced ? wake() : enterSilentMode())}
          className="flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium"
          style={{ backgroundColor: silenced ? "rgba(248,113,113,0.15)" : "rgba(0,212,255,0.12)", color: silenced ? "#f87171" : ACCENT }}
        >
          {silenced ? <MicOff size={13} /> : <Mic size={13} />}
          {silenced ? "Silent" : "Listening"}
        </button>
      </div>

      {showSidebar && (
        <div className="absolute inset-0 z-30 flex">
          <div className="w-72 h-full flex flex-col" style={{ backgroundColor: theme.panel }}>
            <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: theme.border }}>
              <span className="font-semibold" style={{ color: theme.text }}>
                Chats
              </span>
              <button onClick={() => setShowSidebar(false)}>
                <X size={18} style={{ color: theme.text }} />
              </button>
            </div>
            <button
              onClick={newChat}
              className="mx-4 mt-3 mb-2 rounded-xl px-3 py-2 text-sm font-medium flex items-center gap-2 justify-center"
              style={{ backgroundColor: ACCENT, color: DARK_TEXT }}
            >
              <Plus size={16} /> New chat
            </button>
            <div className="flex-1 overflow-y-auto px-2 pb-3">
              {[...conversations]
                .sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || b.updatedAt - a.updatedAt)
                .map((c) => (
                  <div
                    key={c.id}
                    onClick={() => switchConversation(c.id)}
                    className="flex items-center gap-2 px-3 py-2.5 rounded-xl mb-1 cursor-pointer"
                    style={{ backgroundColor: c.id === activeConvId ? "rgba(0,212,255,0.12)" : "transparent" }}
                  >
                    <MessageSquare size={14} style={{ color: theme.subtext, flexShrink: 0 }} />
                    <span className="flex-1 text-sm truncate" style={{ color: theme.text }}>
                      {c.title}
                    </span>
                    <button onClick={(e) => togglePin(c.id, e)}>
                      <Star size={14} fill={c.pinned ? ACCENT : "none"} style={{ color: c.pinned ? ACCENT : theme.subtext }} />
                    </button>
                    <button onClick={(e) => handleDeleteClick(c.id, e)}>
                      <Trash2 size={14} style={{ color: confirmDeleteId === c.id ? "#f87171" : theme.subtext }} />
                    </button>
                  </div>
                ))}
            </div>
          </div>
          <div className="flex-1" onClick={() => setShowSidebar(false)} style={{ backgroundColor: "rgba(0,0,0,0.4)" }} />
        </div>
      )}

      {showAttachSheet && (
        <div className="absolute inset-0 z-20 flex items-end" style={{ backgroundColor: "rgba(0,0,0,0.5)" }} onClick={() => setShowAttachSheet(false)}>
          <div className="w-full rounded-t-2xl p-4" style={{ backgroundColor: theme.panel }} onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-around mb-4">
              <button onClick={openFilePicker} className="flex flex-col items-center gap-1">
                <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: theme.inputBg }}>
                  <Camera size={20} style={{ color: theme.text }} />
                </div>
                <span className="text-xs" style={{ color: theme.text }}>
                  Camera
                </span>
              </button>
              <button onClick={openFilePicker} className="flex flex-col items-center gap-1">
                <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: theme.inputBg }}>
                  <ImageIcon size={20} style={{ color: theme.text }} />
                </div>
                <span className="text-xs" style={{ color: theme.text }}>
                  Photos
                </span>
              </button>
              <button onClick={openFilePicker} className="flex flex-col items-center gap-1">
                <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: theme.inputBg }}>
                  <FileUp size={20} style={{ color: theme.text }} />
                </div>
                <span className="text-xs" style={{ color: theme.text }}>
                  Files
                </span>
              </button>
              <button onClick={captureScreenShare} className="flex flex-col items-center gap-1">
                <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: theme.inputBg }}>
                  <Monitor size={20} style={{ color: theme.text }} />
                </div>
                <span className="text-xs" style={{ color: theme.text }}>
                  Screen
                </span>
              </button>
            </div>
            <div className="flex items-center justify-between py-2 border-t" style={{ borderColor: theme.border }}>
              <div>
                <div className="text-sm" style={{ color: theme.text }}>
                  Web search
                </div>
                <div className="text-xs" style={{ color: theme.subtext }}>
                  Real, current answers with citations
                </div>
              </div>
              <button
                onClick={() => setWebSearchEnabled((v) => !v)}
                className="w-11 h-6 rounded-full relative"
                style={{ backgroundColor: webSearchEnabled ? ACCENT : theme.inputBg }}
              >
                <span
                  className="absolute top-0.5 w-5 h-5 rounded-full"
                  style={{ backgroundColor: "white", left: webSearchEnabled ? "22px" : "2px", transition: "left 0.15s" }}
                />
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === "chat" && (
        <>
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {webSearchEnabled && (
              <div
                className="text-center text-xs py-1 rounded-full mx-auto px-3"
                style={{ backgroundColor: "rgba(0,212,255,0.1)", color: ACCENT, width: "fit-content" }}
              >
                🔎 Web search is on
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className="flex flex-col"
                  style={{ maxWidth: "85%", minWidth: 0, alignItems: m.role === "user" ? "flex-end" : "flex-start" }}
                >
                  <div
                    className="rounded-2xl px-4 py-2 text-sm"
                    style={
                      m.role === "user"
                        ? { backgroundColor: ACCENT, color: DARK_TEXT, minWidth: 0 }
                        : { backgroundColor: theme.panel, color: theme.text, border: `1px solid ${theme.border}`, minWidth: 0 }
                    }
                  >
                    {m.attachmentPreview && m.attachmentKind === "image" && (
                      <img src={m.attachmentPreview} alt="" className="rounded-lg mb-1" style={{ maxWidth: "180px" }} />
                    )}
                    {m.attachmentPreview && m.attachmentKind && m.attachmentKind !== "image" && (
                      <div className="flex items-center gap-1 mb-1 text-xs" style={{ opacity: 0.85 }}>
                        <FileText size={13} /> {m.attachmentPreview}
                      </div>
                    )}
                    {renderMarkdown(m.text, `m${i}`)}
                    {m.image && <img src={m.image} alt="" className="rounded-lg mt-2" style={{ maxWidth: "200px" }} />}
                  </div>
                  <div className="flex items-center gap-2 mt-1 px-1">
                    <span className="text-xs" style={{ color: theme.subtext }}>
                      {formatTime(m.ts)}
                    </span>
                    {m.role === "jarvis" && (
                      <button onClick={() => speakText(m.text)}>
                        <Volume2 size={11} style={{ color: theme.subtext }} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {thinking && (
              <div className="flex justify-start">
                <div className="rounded-2xl px-4 py-3 flex items-center gap-2" style={{ backgroundColor: theme.panel, border: `1px solid ${theme.border}` }}>
                  <span className="text-xs" style={{ color: theme.subtext }}>
                    JARVIS is thinking
                  </span>
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: ACCENT }} />
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: ACCENT, animationDelay: "0.15s" }} />
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: ACCENT, animationDelay: "0.3s" }} />
                </div>
              </div>
            )}
            {silenced && (
              <div className="text-center text-xs py-2" style={{ color: theme.subtext }}>
                🤐 JARVIS is silent. Tap the mic or say "wake up" to resume.
              </div>
            )}
          </div>

          <div className="px-3 pb-3 pt-2">
            {isSpeaking && (
              <button
                onClick={stopSpeaking}
                className="flex items-center gap-2 px-4 py-2 mb-2 rounded-full text-xs font-medium mx-auto"
                style={{ backgroundColor: "rgba(248,113,113,0.15)", color: "#f87171" }}
              >
                <VolumeX size={14} /> Stop speaking
              </button>
            )}
            {attachment && (
              <div className="flex items-center gap-2 px-3 py-2 mb-2 rounded-xl" style={{ backgroundColor: theme.inputBg }}>
                {attachment.kind === "image" ? (
                  <img src={attachment.previewUrl} alt="" className="w-8 h-8 rounded object-cover" />
                ) : (
                  <FileText size={18} style={{ color: ACCENT }} />
                )}
                <span className="text-xs flex-1 truncate" style={{ color: theme.text }}>
                  {attachment.name}
                </span>
                <button onClick={() => setAttachment(null)}>
                  <X size={14} style={{ color: theme.subtext }} />
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 rounded-full px-3 py-2" style={{ backgroundColor: theme.inputBg }}>
              <button onClick={() => setShowAttachSheet(true)}>
                <Paperclip size={17} style={{ color: theme.subtext }} />
              </button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder={silenced ? "Silenced — tap the mic to resume" : listening ? "Listening…" : "Type or speak..."}
                disabled={silenced}
                className="flex-1 bg-transparent outline-none text-sm"
                style={{ color: theme.text }}
              />
              <button
                onClick={silenced ? wake : startVoiceInput}
                style={{ color: silenced ? "#f87171" : listening ? ACCENT : voiceSupported ? theme.subtext : "rgba(150,150,150,0.4)" }}
              >
                <Mic size={17} className={listening ? "animate-pulse" : ""} />
              </button>
              <button onClick={send} disabled={silenced || thinking} style={{ color: silenced || thinking ? "rgba(150,150,150,0.4)" : ACCENT }}>
                <Send size={17} />
              </button>
            </div>
          </div>
        </>
      )}

      {tab === "home" && <HomeView goToChat={() => setTab("chat")} theme={theme} />}
      {tab === "tools" && <ToolsView theme={theme} />}
      {tab === "settings" && <SettingsView theme={theme} themeMode={themeMode} setThemeMode={setThemeMode} />}

      <div className="flex justify-around py-2 border-t" style={{ backgroundColor: theme.tabBg, borderColor: theme.border }}>
        {[
          ["home", Home],
          ["chat", MessageSquare],
          ["tools", Wrench],
          ["settings", Settings],
        ].map(([key, Icon]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className="flex flex-col items-center gap-1 text-xs capitalize"
            style={{ color: tab === key ? ACCENT : theme.subtext }}
          >
            <Icon size={17} />
            {key}
          </button>
        ))}
      </div>
    </div>
  );
}
