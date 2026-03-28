interface BuildInfo {
  generated_utc?: string;
  repository?: string;
  commit_sha?: string;
  commit_short?: string;
  commit_url?: string;
  run_id?: string;
  run_url?: string;
  warnings?: string[];
}

interface FeedLink {
  label: string;
  toml: string;
  html: string;
  json: string;
}

interface BootstrapData {
  username: string;
  generated_utc?: string;
  build_info?: BuildInfo;
  links?: FeedLink[];
}

interface RepoInventoryItem {
  full: string;
  desc?: string;
  topics?: string[];
  lang?: string;
  stars: number;
  forks: number;
  open_issues: number;
  pushed_utc: string;
  homepage?: string;
  default_branch: string;
  readme?: string;
  changelog?: string;
  recent_files?: string[];
}

interface InventoryData {
  username: string;
  generated_utc: string;
  repo: RepoInventoryItem[];
}

interface RepoTodosItem {
  full: string;
  todos?: string[];
  synopsis?: string[];
}

interface TodosData {
  username: string;
  generated_utc: string;
  repo: RepoTodosItem[];
}

interface ActivitySummary {
  events: number;
  repos: number;
  pushes: number;
  pull_requests: number;
  issues: number;
  comments: number;
  releases: number;
  stars: number;
  creates: number;
  deletes: number;
}

interface ActivityInsights {
  streak_days: number;
  busiest_local_day?: string;
  top_repos: string[];
  top_event_types: string[];
}

interface ActivityEvent {
  type: string;
  repo_owner: string;
  repo_name: string;
  at_utc: string;
  url: string;
  title: string;
  commits?: string[];
  event_id: string;
}

interface ActivityData {
  username: string;
  generated_utc: string;
  window_start_utc: string;
  window_days: number;
  summary: ActivitySummary;
  insights: ActivityInsights;
  event: ActivityEvent[];
}

interface AppData {
  inventory: InventoryData;
  todos: TodosData;
  activity7d: ActivityData;
  activity30d: ActivityData;
}

interface SlideDefinition {
  id: string;
  shortTitle: string;
  stageLabel: string;
  deckCopy: string;
  render: () => string;
}

interface Window {
  GH_STATUS_BOOTSTRAP?: BootstrapData;
}

((): void => {
  const bootstrap = window.GH_STATUS_BOOTSTRAP ?? { username: "unknown" };
  const state = {
    mode: "7d" as "7d" | "30d",
    index: 0,
    decks: {
      "7d": [] as SlideDefinition[],
      "30d": [] as SlideDefinition[],
    },
  };

  const slideFrame = document.getElementById("slide-frame");
  const slideList = document.getElementById("slide-list");
  const deckLabel = document.getElementById("deck-label");
  const deckMeta = document.getElementById("deck-meta");
  const sidebarTitle = document.getElementById("sidebar-title");
  const sidebarCopy = document.getElementById("sidebar-copy");
  const counter = document.getElementById("slide-counter");
  const progressBar = document.getElementById("deck-progress-bar");
  const mode7Button = document.getElementById("mode-7d") as HTMLButtonElement | null;
  const mode30Button = document.getElementById("mode-30d") as HTMLButtonElement | null;
  const nextButton = document.getElementById("next-slide") as HTMLButtonElement | null;
  const prevButton = document.getElementById("prev-slide") as HTMLButtonElement | null;

  if (!slideFrame || !slideList || !deckLabel || !deckMeta || !sidebarTitle || !sidebarCopy || !counter || !progressBar) {
    return;
  }

  const todoMap = new Map<string, RepoTodosItem>();

  void initialize();

  async function initialize(): Promise<void> {
    try {
      const [inventory, todos, activity7d, activity30d] = await Promise.all([
        fetchJson<InventoryData>("inventory.json"),
        fetchJson<TodosData>("todos.json"),
        fetchJson<ActivityData>("latest-7d.json"),
        fetchJson<ActivityData>("latest-30d.json"),
      ]);

      for (const repo of todos.repo) {
        todoMap.set(repo.full, repo);
      }

      const data: AppData = { inventory, todos, activity7d, activity30d };
      state.decks["7d"] = buildDeck(data, "7d");
      state.decks["30d"] = buildDeck(data, "30d");
      wireControls();
      render();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      slideFrame!.innerHTML = `
        <div class="error">
          <div>
            <div class="eyebrow">Deck unavailable</div>
            <h2 style="margin-top: 10px;">Could not load the generated feed files</h2>
            <p class="lede">${escapeHtml(message)}</p>
          </div>
        </div>
      `;
    }
  }

  function wireControls(): void {
    mode7Button?.addEventListener("click", () => {
      if (state.mode !== "7d") {
        state.mode = "7d";
        state.index = 0;
        render();
      }
    });

    mode30Button?.addEventListener("click", () => {
      if (state.mode !== "30d") {
        state.mode = "30d";
        state.index = 0;
        render();
      }
    });

    nextButton?.addEventListener("click", () => goTo(state.index + 1));
    prevButton?.addEventListener("click", () => goTo(state.index - 1));

    document.addEventListener("keydown", (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") {
        event.preventDefault();
        goTo(state.index + 1);
      }

      if (event.key === "ArrowLeft" || event.key === "PageUp") {
        event.preventDefault();
        goTo(state.index - 1);
      }
    });
  }

  function buildDeck(data: AppData, mode: "7d" | "30d"): SlideDefinition[] {
    const activity = mode === "7d" ? data.activity7d : data.activity30d;
    const eventLimit = mode === "7d" ? 5 : 10;
    const hotRepos = data.inventory.repo.slice(0, 3);
    const todoLeaders = [...data.todos.repo]
      .filter((repo) => (repo.todos?.length ?? 0) > 0)
      .sort((left, right) => (right.todos?.length ?? 0) - (left.todos?.length ?? 0))
      .slice(0, 6);

    const slides: SlideDefinition[] = [
      overviewSlide(data),
      pulseSlide(data.inventory, activity, mode),
      repoLandscapeSlide(data.inventory, data.todos, activity),
      ...hotRepos.map((repo, index) => hotRepoSlide(repo, index + 1)),
      ...activity.event.slice(0, eventLimit).map((event, index) => eventSlide(event, index + 1, activity.window_days)),
      todoSlide(todoLeaders, mode),
      sourceSlide(mode),
    ];

    return slides;
  }

  function overviewSlide(data: AppData): SlideDefinition {
    const todoCount = data.todos.repo.reduce((sum, repo) => sum + (repo.todos?.length ?? 0), 0);
    const topRepo = data.activity30d.insights.top_repos[0]?.split(":")[0] ?? "No clear leader";
    const generated = formatDateTime(data.inventory.generated_utc);

    return {
      id: "overview",
      shortTitle: "Overview",
      stageLabel: "Opening frame",
      deckCopy: "Start with the broad shape of the work: scale, momentum, and where the center of gravity sits right now.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">Snapshot</div>
          <h1>${escapeHtml(data.inventory.username)} on GitHub, lately.</h1>
          <p class="lede">
            This deck is assembled in the browser from nightly generated static files. The short version gives a fast weekly briefing;
            the long version stretches into a monthly retrospective you can click through like a status presentation.
          </p>
          <div class="hero-stats">
            <section class="stat-card">
              <div class="card-label">Public repos</div>
              <span class="stat-value">${data.inventory.repo.length}</span>
              <div class="detail">Tracked from the inventory feed.</div>
            </section>
            <section class="stat-card">
              <div class="card-label">Open TODO items</div>
              <span class="stat-value">${todoCount}</span>
              <div class="detail">Collected from public repo planning files.</div>
            </section>
            <section class="stat-card">
              <div class="card-label">7-day events</div>
              <span class="stat-value">${data.activity7d.summary.events}</span>
              <div class="detail">A quick pulse on what changed this week.</div>
            </section>
            <section class="stat-card">
              <div class="card-label">30-day lead repo</div>
              <span class="stat-value" style="font-size: clamp(1.2rem, 2.4vw, 2rem); line-height: 1.2;">${escapeHtml(topRepo)}</span>
              <div class="detail">Most represented repo across the recent event feed.</div>
            </section>
          </div>
          <div class="quote-card">
            <strong>Generated:</strong> ${escapeHtml(generated)}<br>
            <strong>Build:</strong> ${escapeHtml(bootstrap.build_info?.commit_short ?? "local")}<br>
            <strong>Deck idea:</strong> show the summary first, then turn recent activity into a sequence of moments instead of a single wall of stats.
          </div>
        </article>
      `,
    };
  }

  function pulseSlide(inventory: InventoryData, activity: ActivityData, mode: "7d" | "30d"): SlideDefinition {
    const topRepos = activity.insights.top_repos.slice(0, 3);
    const topEventTypes = activity.insights.top_event_types.slice(0, 3);
    const freshest = inventory.repo.slice(0, 4).map((repo) => `${repo.full} (${formatShortDate(repo.pushed_utc)})`);

    return {
      id: `${mode}-pulse`,
      shortTitle: `${mode === "7d" ? "Weekly" : "Monthly"} pulse`,
      stageLabel: `${activity.window_days}-day activity pulse`,
      deckCopy: "This slide compresses the activity feed into the few signals that help orient the rest of the slideshow.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">${activity.window_days}-day pulse</div>
          <h2>${mode === "7d" ? "Short, current, directional." : "Longer, calmer, more patterned."}</h2>
          <p class="lede">
            ${mode === "7d"
              ? "Weekly mode is for the quick walkthrough: what moved, which repos surfaced, and whether the cadence is active right now."
              : "Monthly mode lets the same feed breathe a little, so repo clusters and event patterns are easier to notice."}
          </p>
          <div class="fact-grid">
            <section class="fact-card">
              <div class="card-label">Events</div>
              <span class="fact-value">${activity.summary.events}</span>
              <div class="detail">${activity.summary.repos} repos touched in this window.</div>
            </section>
            <section class="fact-card">
              <div class="card-label">Streak</div>
              <span class="fact-value">${activity.insights.streak_days}</span>
              <div class="detail">Consecutive active local days.</div>
            </section>
            <section class="fact-card">
              <div class="card-label">Busiest day</div>
              <span class="fact-value" style="font-size: clamp(1.2rem, 2.2vw, 1.8rem);">${escapeHtml(activity.insights.busiest_local_day ?? "None")}</span>
              <div class="detail">Local-date activity peak.</div>
            </section>
            <section class="fact-card">
              <div class="card-label">Pull requests</div>
              <span class="fact-value">${activity.summary.pull_requests}</span>
              <div class="detail">${activity.summary.deletes} deletes and ${activity.summary.comments} comments also surfaced.</div>
            </section>
          </div>
          <div class="repo-grid">
            <section class="repo-card">
              <div class="card-label">Top repos</div>
              <ul class="list">${topRepos.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
            <section class="repo-card">
              <div class="card-label">Top event types</div>
              <ul class="list">${topEventTypes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
            <section class="repo-card">
              <div class="card-label">Fresh inventory</div>
              <ul class="list">${freshest.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
          </div>
        </article>
      `,
    };
  }

  function repoLandscapeSlide(inventory: InventoryData, todos: TodosData, activity: ActivityData): SlideDefinition {
    const repoCards = inventory.repo.slice(0, 6).map((repo) => {
      const todoEntry = todoMap.get(repo.full);
      const todoCount = todoEntry?.todos?.length ?? 0;
      const synopsis = firstMeaningfulText(todoEntry?.synopsis) ?? firstMeaningfulText(extractReadmeSentences(repo.readme, 2)) ?? "No synopsis yet.";
      return `
        <section class="repo-card">
          <div class="event-top">
            <span class="repo-chip">${escapeHtml(repo.lang ?? "Unknown")}</span>
            <span class="repo-chip">${repo.stars} stars</span>
            <span class="repo-chip">${todoCount} TODOs</span>
          </div>
          <h3 style="margin: 14px 0 8px; font-size: 1.2rem;"><a href="https://github.com/${escapeHtml(repo.full)}">${escapeHtml(repo.full)}</a></h3>
          <p class="detail">${escapeHtml(repo.desc ?? "No description provided.")}</p>
          <div class="detail">${escapeHtml(synopsis)}</div>
        </section>
      `;
    }).join("");

    const activeLabel = activity.insights.top_repos[0] ?? "No standout repo yet";
    const todoCount = todos.repo.reduce((sum, repo) => sum + (repo.todos?.length ?? 0), 0);

    return {
      id: "landscape",
      shortTitle: "Repo landscape",
      stageLabel: "Repository landscape",
      deckCopy: "A slide for the broader project surface: the most recently pushed repos, their shape, and what looks warm.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">Landscape</div>
          <h2>What the repo surface feels like right now.</h2>
          <p class="lede">
            The inventory feed acts like a static database: it gives us the freshest repos, descriptions, language mix, stars, issues,
            and a small amount of rich content for the hottest projects. That is enough to make the deck feel editorial instead of raw.
          </p>
          <div class="quote-card">
            <strong>Current lead signal:</strong> ${escapeHtml(activeLabel)}<br>
            <strong>Total TODO volume:</strong> ${todoCount}<br>
            <strong>Design move:</strong> use inventory + TODOs for the setup, then activity events for the click-through middle.
          </div>
          <div class="repo-grid">${repoCards}</div>
        </article>
      `,
    };
  }

  function hotRepoSlide(repo: RepoInventoryItem, order: number): SlideDefinition {
    const todoEntry = todoMap.get(repo.full);
    const synopsis = (todoEntry?.synopsis?.slice(0, 3) ?? extractReadmeSentences(repo.readme, 3)).slice(0, 3);
    const todos = (todoEntry?.todos ?? []).slice(0, 4);
    const recentFiles = (repo.recent_files ?? []).slice(0, 5);
    const changelogHead = extractChangelogHeading(repo.changelog);

    return {
      id: `repo-${order}-${repo.full.replace(/[^\w-]+/g, "-")}`,
      shortTitle: `Hot repo ${order}`,
      stageLabel: `Hot repo ${order}`,
      deckCopy: "Each hot repo gets its own beat in the slideshow so the deck can pause on a project instead of flattening everything into totals.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">Hot repo ${order}</div>
          <h2>${escapeHtml(repo.full)}</h2>
          <p class="lede">${escapeHtml(repo.desc ?? "No repository description was available.")}</p>
          <div class="fact-grid">
            <section class="fact-card">
              <div class="card-label">Language</div>
              <span class="fact-value" style="font-size: clamp(1.2rem, 2vw, 1.8rem);">${escapeHtml(repo.lang ?? "Unknown")}</span>
              <div class="detail">Pushed ${escapeHtml(formatDateTime(repo.pushed_utc))}</div>
            </section>
            <section class="fact-card">
              <div class="card-label">Social</div>
              <span class="fact-value">${repo.stars}</span>
              <div class="detail">${repo.forks} forks, ${repo.open_issues} open issues.</div>
            </section>
            <section class="fact-card">
              <div class="card-label">TODOs</div>
              <span class="fact-value">${todoEntry?.todos?.length ?? 0}</span>
              <div class="detail">Public planning items extracted from this repo.</div>
            </section>
            <section class="fact-card">
              <div class="card-label">Changelog</div>
              <span class="fact-value" style="font-size: clamp(1rem, 1.8vw, 1.5rem); line-height: 1.3;">${escapeHtml(changelogHead ?? "No changelog heading")}</span>
              <div class="detail">Latest visible heading or fallback label.</div>
            </section>
          </div>
          <div class="repo-grid">
            <section class="repo-card">
              <div class="card-label">Synopsis</div>
              <ul class="list">${renderList(synopsis, "No synopsis extracted yet.")}</ul>
            </section>
            <section class="repo-card">
              <div class="card-label">Recent files</div>
              <ul class="list">${renderList(recentFiles, "No recent file list available.")}</ul>
            </section>
            <section class="repo-card">
              <div class="card-label">Next up</div>
              <ul class="list">${renderList(todos, "No public TODO items found.")}</ul>
            </section>
          </div>
        </article>
      `,
    };
  }

  function eventSlide(event: ActivityEvent, order: number, windowDays: number): SlideDefinition {
    const commitList = (event.commits ?? []).slice(0, 4);
    const repoFull = `${event.repo_owner}/${event.repo_name}`;

    return {
      id: `event-${event.event_id}`,
      shortTitle: `Event ${order}`,
      stageLabel: `${windowDays}-day event stream`,
      deckCopy: "This is the middle of the deck: one event per slide so the recent history reads like a sequence instead of a dump.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">Recent event ${order}</div>
          <h2>${escapeHtml(event.title)}</h2>
          <div class="event-card">
            <div class="event-top">
              <span class="event-pill">${escapeHtml(event.type)}</span>
              <span class="repo-chip">${escapeHtml(repoFull)}</span>
              <span class="repo-chip">${escapeHtml(formatDateTime(event.at_utc))}</span>
            </div>
            <p class="detail">
              The event feed is already ordered newest-first, so advancing through these slides becomes a tiny retrospective of what the public graph saw.
            </p>
            ${commitList.length > 0 ? `<ul class="list">${commitList.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
            <div>
              <a class="link-button" href="${escapeAttribute(event.url)}">Open on GitHub</a>
            </div>
          </div>
        </article>
      `,
    };
  }

  function todoSlide(todoLeaders: RepoTodosItem[], mode: "7d" | "30d"): SlideDefinition {
    const cards = todoLeaders.map((repo) => `
      <section class="todo-card">
        <div class="card-label">${escapeHtml(repo.full)}</div>
        <ul class="list">${renderList((repo.todos ?? []).slice(0, mode === "7d" ? 3 : 5), "No TODO entries.")}</ul>
      </section>
    `).join("");

    return {
      id: "todos",
      shortTitle: "What next",
      stageLabel: "Closing backlog frame",
      deckCopy: "A good ending slide answers what happens after the retrospective. The TODO feed makes that easy.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">What next</div>
          <h2>End on the backlog, not just the scoreboard.</h2>
          <p class="lede">
            The weekly deck can end with the closest next moves. The monthly deck can linger a bit longer and show more TODO detail.
            This gives the site a clean narrative arc: overview, recent motion, project focus, then next actions.
          </p>
          <div class="todo-grid">
            ${cards || `<section class="todo-card"><div class="detail">No public TODO items were found in the generated feed.</div></section>`}
          </div>
        </article>
      `,
    };
  }

  function sourceSlide(mode: "7d" | "30d"): SlideDefinition {
    const links = bootstrap.links ?? [];
    return {
      id: "sources",
      shortTitle: "Feed files",
      stageLabel: "Source files",
      deckCopy: "The browser app is just one reading of the data. The raw TOML and JSON still stay first-class for humans and agents.",
      render: () => `
        <article class="slide is-active">
          <div class="slide-kicker">Source files</div>
          <h2>${mode === "7d" ? "Short deck, open data." : "Long deck, open data."}</h2>
          <p class="lede">
            The whole trick here is not a heavy app. It is generated static data plus a lightweight client that chooses a presentation.
            The nightly run keeps publishing TOML for agent ingestion and JSON for the slideshow.
          </p>
          <div class="feed-grid">
            ${links.map((link: { label: string; json: string; toml: string; html: string }) => `
              <section class="feed-card">
                <div class="card-label">${escapeHtml(link.label)}</div>
                <div class="detail"><a href="${escapeAttribute(link.json)}">JSON</a> for the browser deck.</div>
                <div class="detail"><a href="${escapeAttribute(link.toml)}">TOML</a> for raw data.</div>
                <div class="detail"><a href="${escapeAttribute(link.html)}">HTML wrapper</a> for readable source.</div>
              </section>
            `).join("")}
          </div>
        </article>
      `,
    };
  }

  function render(): void {
    const slides = state.decks[state.mode];
    if (!slides.length) {
      return;
    }

    state.index = clamp(state.index, 0, slides.length - 1);
    const currentSlide = slides[state.index];
    slideFrame!.innerHTML = currentSlide.render();

    deckLabel!.textContent = state.mode === "7d" ? "Weekly deck" : "Monthly deck";
    deckMeta!.innerHTML = `
      <span class="meta-chip">${slides.length} slides</span>
      <span class="meta-chip">${state.mode === "7d" ? "Designed as a short walkthrough" : "Designed as a longer retrospective"}</span>
      <span class="meta-chip">Generated ${escapeHtml(formatDateTime(bootstrap.generated_utc ?? bootstrap.build_info?.generated_utc ?? ""))}</span>
    `;

    sidebarTitle!.textContent = state.mode === "7d" ? "Weekly outline" : "Monthly outline";
    sidebarCopy!.textContent = currentSlide.deckCopy;
    counter!.textContent = `${state.index + 1} / ${slides.length}`;
    progressBar!.style.width = `${((state.index + 1) / slides.length) * 100}%`;

    slideList!.innerHTML = slides.map((slide, index) => `
      <button type="button" class="slide-jump ${index === state.index ? "is-active" : ""}" data-index="${index}">
        ${index + 1}. ${escapeHtml(slide.shortTitle)}
      </button>
    `).join("");

    for (const button of Array.from(slideList!.querySelectorAll<HTMLButtonElement>("[data-index]"))) {
      button.addEventListener("click", () => {
        const rawIndex = button.dataset.index;
        goTo(rawIndex ? Number.parseInt(rawIndex, 10) : 0);
      });
    }

    if (mode7Button && mode30Button) {
      mode7Button.classList.toggle("is-active", state.mode === "7d");
      mode30Button.classList.toggle("is-active", state.mode === "30d");
    }

    if (prevButton && nextButton) {
      prevButton.disabled = state.index === 0;
      nextButton.disabled = state.index === slides.length - 1;
    }
  }

  function goTo(index: number): void {
    const slides = state.decks[state.mode];
    if (!slides.length) {
      return;
    }
    state.index = clamp(index, 0, slides.length - 1);
    render();
  }

  async function fetchJson<T>(path: string): Promise<T> {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Request for ${path} failed with ${response.status}.`);
    }
    return response.json() as Promise<T>;
  }

  function renderList(items: string[], fallback: string): string {
    if (!items.length) {
      return `<li>${escapeHtml(fallback)}</li>`;
    }
    return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  }

  function extractReadmeSentences(content?: string, count = 3): string[] {
    if (!content) {
      return [];
    }

    return content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => Boolean(line) && !line.startsWith("#") && !line.startsWith("```"))
      .slice(0, count);
  }

  function extractChangelogHeading(content?: string): string | null {
    if (!content) {
      return null;
    }

    const line = content
      .split(/\r?\n/)
      .map((item) => item.trim())
      .find((item) => item.startsWith("## "));

    return line ? line.replace(/^##\s+/, "") : null;
  }

  function firstMeaningfulText(items?: string[]): string | null {
    const value = items?.find((item) => item.trim().length > 0);
    return value ?? null;
  }

  function formatDateTime(value?: string): string {
    if (!value) {
      return "unknown";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function formatShortDate(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
    }).format(date);
  }

  function clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }

  function escapeHtml(value: string): string {
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeAttribute(value: string): string {
    return escapeHtml(value);
  }
})();
