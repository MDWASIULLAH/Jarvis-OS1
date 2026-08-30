import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import os from "os";
import path from "path";

export async function POST(req: NextRequest) {
  try {
    const { command, cwd } = await req.json();
    if (!command || typeof command !== "string") {
      return NextResponse.json({ error: "Command required" }, { status: 400 });
    }

    const workingDir = cwd && path.isAbsolute(cwd) ? cwd : process.cwd();
    const isWindows = os.platform() === "win32";
    const shell = isWindows ? "powershell.exe" : "/bin/bash";

    return new Promise<NextResponse>((resolve) => {
      exec(
        command,
        {
          cwd: workingDir,
          shell: isWindows ? "powershell.exe" : undefined,
          timeout: 15000,
          maxBuffer: 1024 * 1024 * 5, // 5MB output
        },
        (error, stdout, stderr) => {
          resolve(
            NextResponse.json({
              stdout: stdout || "",
              stderr: stderr || (error ? error.message : ""),
              exitCode: error ? error.code ?? 1 : 0,
              cwd: workingDir,
              os: os.platform(),
              user: os.userInfo().username,
              hostname: os.hostname(),
            })
          );
        }
      );
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to execute command" },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    platform: os.platform(),
    type: os.type(),
    user: os.userInfo().username,
    homedir: os.homedir(),
    cwd: process.cwd(),
    hostname: os.hostname(),
  });
}
