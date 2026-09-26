class Almanac < Formula
  desc "Persistent memory layer for AI coding agents"
  homepage "https://github.com/AndriGitDev/almanac"
  url "https://github.com/AndriGitDev/almanac/archive/refs/tags/v5.1.0.tar.gz"
  # sha256 "UPDATE_WITH_ACTUAL_SHA256_AFTER_RELEASE"
  license "MIT"
  head "https://github.com/AndriGitDev/almanac.git", branch: "main"

  depends_on "git"
  depends_on "python@3"

  def install
    # Install the full project tree into libexec
    ignored_hidden_files = %w[. .. .git]
    libexec.install Dir["*"]
    libexec.install Dir[".*"].reject { |f| ignored_hidden_files.include?(File.basename(f)) }

    # Link the CLI wrapper
    bin.install_symlink libexec/"bin/almanac"
  end

  def caveats
    <<~EOS
      To complete setup, run:
        almanac install

      This will configure agent hooks, skills, and initialize your vault.

      Optional flags:
        almanac install --experimental   # Tenet retrieval + Inception consolidation
        almanac install --mcp            # MCP server (Cursor, Windsurf, Claude Code, etc.)
        almanac install --remote URL     # Connect to a remote vault
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/almanac version").strip
    assert_match "Usage: almanac warmup", shell_output("#{bin}/almanac warmup --help")
  end
end
