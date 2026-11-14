import { NextRequest, NextResponse } from "next/server";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

// Resolve the skills directory — works in dev (repo/) and prod (~/clawd/skills/)
function getSkillsDir(): string {
  if (process.env.SKILLS_DIR) return process.env.SKILLS_DIR;
  // Prod: ~/clawd/skills/ (check first — most specific)
  const homeDir = process.env.HOME || "/home/nobody";
  const prodDir = path.join(homeDir, "clawd", "skills");
  if (fs.existsSync(prodDir)) return prodDir;
  // Dev: cwd is web/, go up 2 levels (web/ → erpclaw-web/ → repo/)
  const repoDir = path.resolve(process.cwd(), "../..");
  if (fs.existsSync(repoDir)) return repoDir;
  return prodDir;
}

function modulesDir(): string {
  if (process.env.ERPCLAW_MODULES_DIR) return process.env.ERPCLAW_MODULES_DIR;
  if (process.env.ERPCLAW_HOME) return path.join(process.env.ERPCLAW_HOME, "modules");
  const homeDir = process.env.HOME || "/home/nobody";
  return path.join(homeDir, ".openclaw", "erpclaw", "modules");
}

// Backend API URL. On Railway this is the API service's private URL, read
// when the request is handled, not when the image is built.
const API_URL = process.env.API_INTERNAL_URL || process.env.API_URL || "http://127.0.0.1:8001";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ skill: string }> }
) {
  const { skill } = await params;

  // Sanitize skill name
  if (!/^[a-z0-9-]+$/.test(skill)) {
    return NextResponse.json({ error: "Invalid skill name" }, { status: 400 });
  }

  const skillsDir = getSkillsDir();
  let yamlPath = path.join(skillsDir, skill, "UI.yaml");

  // Fallback: ERPClaw modules directory (ERPCLAW_HOME or the OpenClaw default)
  if (!fs.existsSync(yamlPath)) {
    const modulesPath = path.join(modulesDir(), skill, "UI.yaml");
    if (fs.existsSync(modulesPath)) {
      yamlPath = modulesPath;
    }
  }

  // Path 1: Hand-written UI.yaml exists — serve it directly
  if (fs.existsSync(yamlPath)) {
    try {
      const content = fs.readFileSync(yamlPath, "utf-8");
      const parsed = yaml.load(content);
      return NextResponse.json(parsed, {
        headers: {
          "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
        },
      });
    } catch {
      return NextResponse.json(
        { error: "Failed to parse UI.yaml" },
        { status: 500 }
      );
    }
  }

  // Path 2: No UI.yaml — ask backend to auto-generate from SKILL.md
  try {
    const res = await fetch(`${API_URL}/api/v1/schema/ui-config/${skill}`, {
      headers: { "Accept": "application/json" },
      // Short timeout — generation should be fast (SKILL.md parsing + inference)
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return NextResponse.json(
        { error: body.error || `UI generation failed (${res.status})`, generated: false },
        { status: res.status }
      );
    }

    const config = await res.json();
    return NextResponse.json(config, {
      headers: {
        "Cache-Control": "public, max-age=300, stale-while-revalidate=600",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Could not generate UI config", skill },
      { status: 404 }
    );
  }
}
