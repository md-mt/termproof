import { defineConfig } from "vitepress";

export default defineConfig({
  title: "TermProof",
  description: "Evidence-first verification for terminal and TUI applications.",
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: "Guide", link: "/getting-started" },
      { text: "API", link: "/api/" },
      { text: "Plugins", link: "/plugins" },
      { text: "CI", link: "/ci/" },
      { text: "GitHub", link: "https://github.com/md-mt/termproof" }
    ],
    sidebar: [
      {
        text: "Getting Started",
        items: [
          { text: "Overview", link: "/" },
          { text: "Install and Run", link: "/getting-started" },
          { text: "Homebrew", link: "/install/homebrew" },
          { text: "FAQ", link: "/faq" }
        ]
      },
      {
        text: "Guides",
        items: [
          { text: "Framework Guides", link: "/guides/" },
          { text: "Textual", link: "/guides/textual" },
          { text: "Bubble Tea", link: "/guides/bubbletea" },
          { text: "Ratatui", link: "/guides/ratatui" }
        ]
      },
      {
        text: "Reference",
        items: [
          { text: "API Reference", link: "/api/" },
          { text: "Plugins", link: "/plugins" },
          { text: "CI Integration", link: "/ci/" }
        ]
      }
    ],
    socialLinks: [
      { icon: "github", link: "https://github.com/md-mt/termproof" }
    ]
  }
});
