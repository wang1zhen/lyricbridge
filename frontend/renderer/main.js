const dom = {
  preciseForm: document.querySelector("#precise-search-form"),
  searchSummary: document.querySelector("#search-summary"),
  songInfo: document.querySelector("#song-info"),
  songTitle: document.querySelector("#song-title"),
  songMeta: document.querySelector("#song-meta"),
  lyricViewer: document.querySelector("#lyric-viewer"),
  searchResults: document.querySelector("#search-results"),
  consoleOutput: document.querySelector("#console-output"),
  exportLyrics: document.querySelector("#export-lyrics"),
  fetchLinks: document.querySelector("#fetch-links"),
  fetchPics: document.querySelector("#fetch-pics"),
  searchText: document.querySelector("#search-text"),
  searchType: document.querySelector("#search-type")
};

const state = {
  preciseResults: [],
  lastPrecisePayload: null
};

const formatDuration = (durationMs) => {
  if (!durationMs) return "未知时长";
  const seconds = Math.floor(durationMs / 1000);
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
};

const joinSinger = (singers = []) => singers.join(" / ") || "未知歌手";

const renderSummary = (summary) => {
  if (!summary) {
    dom.searchSummary.textContent = "";
    dom.searchSummary.classList.remove("error");
    return;
  }
  if (summary.success) {
    // 成功时不展示“success”或提示，保持摘要区域为空
    dom.searchSummary.textContent = "";
    dom.searchSummary.classList.remove("error");
  } else {
    dom.searchSummary.textContent = summary.error || summary.data || "操作失败";
    dom.searchSummary.classList.add("error");
  }
};

const renderResults = (response) => {
  state.preciseResults = response.results || [];

  // Render single-song header + lyric viewer (Material style)
  const first = state.preciseResults[0];
  if (first) {
    const { song, lyric, duration_ms } = first;
    dom.songTitle.textContent = song.name || "未知歌曲";
    dom.songMeta.textContent = `${joinSinger(song.singer)} · ${song.album || "未知专辑"} · ${formatDuration(duration_ms)}`;
    const text = (lyric && (lyric.origin || lyric.translation || lyric.transliteration)) || "";
    const srt = lrcToSrt(text);
    dom.lyricViewer.textContent = srt || text;
  } else {
    dom.songTitle.textContent = "";
    dom.songMeta.textContent = "";
    dom.lyricViewer.textContent = "";
  }

  if (dom.searchResults) dom.searchResults.innerHTML = "";

  if (dom.searchResults && !state.preciseResults.length && !Object.keys(response.errors || {}).length) {
    dom.searchResults.innerHTML = `<p class="error">无查询结果</p>`;
  }

  for (const bundle of state.preciseResults) {
    const card = document.createElement("article");
    card.className = "result-card";

    const header = document.createElement("header");
    header.innerHTML = `
      <div>
        <strong>${bundle.song.name}</strong>
        <div class="meta">${joinSinger(bundle.song.singer)} · ${bundle.song.album || "未知专辑"} · ${formatDuration(
      bundle.duration_ms
    )}</div>
      </div>
      <div class="badges">
        <span class="badge">${bundle.song.display_id}</span>
        <span class="badge">${bundle.song.id}</span>
      </div>
    `;

    const lyricSection = document.createElement("pre");
    lyricSection.className = "console-output";
    const lyric = bundle.lyric || {};
    lyricSection.textContent =
      lyric.origin ||
      lyric.translation ||
      lyric.transliteration ||
      "(歌词内容将在完整实现后显示，此处为占位提示)";

    card.appendChild(header);
    card.appendChild(lyricSection);

    if (dom.searchResults) dom.searchResults.appendChild(card);
  }

  const errorEntries = Object.entries(response.errors || {});
  if (dom.searchResults && errorEntries.length) {
    const errorBlock = document.createElement("pre");
    errorBlock.className = "console-output error";
    errorBlock.textContent = errorEntries
      .map(([id, message]) => `[${id}] ${message}`)
      .join("\n");
    dom.searchResults.appendChild(errorBlock);
  }

  if (dom.consoleOutput) dom.consoleOutput.textContent = response.console_output || "";
  renderSummary(response.summary);
};

// Convert LRC-like timestamps to SRT for display
function lrcToSrt(text) {
  if (!text || typeof text !== "string") return "";
  const lines = text.split(/\r?\n/);
  const entries = [];
  const timeRe = /\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]/g;
  for (const raw of lines) {
    let lastIndex = 0;
    let m;
    const times = [];
    while ((m = timeRe.exec(raw))) {
      const mm = parseInt(m[1], 10) || 0;
      const ss = parseInt(m[2], 10) || 0;
      const ms = m[3] ? parseInt(m[3].padEnd(3, '0').slice(0,3), 10) : 0;
      times.push(mm * 60000 + ss * 1000 + ms);
      lastIndex = m.index + m[0].length;
    }
    const content = raw.slice(lastIndex).trim();
    if (times.length && content) {
      for (const t of times) entries.push({ t, content });
    }
  }
  if (!entries.length) return "";
  entries.sort((a, b) => a.t - b.t);
  const toStamp = (ms) => {
    const hh = Math.floor(ms / 3600000);
    const mm = Math.floor((ms % 3600000) / 60000);
    const ss = Math.floor((ms % 60000) / 1000);
    const mmm = Math.max(0, ms % 1000);
    const pad = (n, w=2) => String(n).padStart(w, '0');
    return `${pad(hh)}:${pad(mm)}:${pad(ss)},${pad(mmm,3)}`;
  };
  const srt = [];
  for (let i = 0; i < entries.length; i++) {
    const start = entries[i].t;
    const end = (i + 1 < entries.length ? entries[i + 1].t : start + 3000) - 1;
    srt.push(String(i + 1));
    srt.push(`${toStamp(start)} --> ${toStamp(Math.max(end, start + 500))}`);
    srt.push(entries[i].content);
    srt.push("");
  }
  return srt.join("\n");
}

const handlePreciseSearch = async (ev) => {
  ev.preventDefault();
  const url = dom.searchText.value.trim();
  const payload = {
    search_text: url,
    // 后端会根据 URL 自动判断来源；类型固定为单曲
    search_type: dom.searchType ? dom.searchType.value : "song"
  };

  // 简单校验：要求为 URL
  if (!/^https?:\/\//i.test(url)) {
    renderSummary({ success: false, error: "请输入有效的歌曲链接（URL）" });
    return;
  }

  state.lastPrecisePayload = payload;

  try {
    dom.searchSummary.textContent = "查询中...";
    const response = await window.api.preciseSearch(payload);
    renderResults(response);
  } catch (error) {
    dom.searchSummary.textContent = error.message;
    dom.searchSummary.classList.add("error");
  }
};

// 已移除模糊搜索

const handleExport = async () => {
  if (!state.preciseResults.length) {
    renderSummary({ success: false, error: "您必须先搜索，才能保存内容" });
    return;
  }
  const first = state.preciseResults[0];
  const lyric = first && first.lyric ? (first.lyric.origin || first.lyric.translation || first.lyric.transliteration || "") : "";
  const srt = lrcToSrt(lyric) || lyric;
  if (!srt.trim()) {
    renderSummary({ success: false, error: "没有可保存的歌词内容" });
    return;
  }
  const sanitize = (name) => name.replace(/[<>:"/\\|?*]+/g, "_").trim() || "lyric";
  const defaultFileName = `${sanitize(first.song.name || first.song.display_id || first.song.id)}.srt`;
  const result = await window.api.saveSrt(defaultFileName, srt);
  if (result && result.error) {
    renderSummary({ success: false, error: result.error });
  } else if (result && !result.canceled) {
    renderSummary({ success: true, data: "歌词已保存" });
  }
};

const handleSongLinks = async () => {
  if (!state.preciseResults.length) {
    renderSummary({ success: false, error: "您必须先搜索，才能获取歌曲链接" });
    return;
  }
  const payload = {
    songs: state.preciseResults.map((bundle) => ({
      id: bundle.song.id,
      display_id: bundle.song.display_id,
      search_source: bundle.lyric.search_source
    }))
  };
  try {
    const response = await window.api.getSongLinks(payload);
    dom.consoleOutput.textContent = JSON.stringify(response.assets, null, 2);
    renderSummary(response.summary);
  } catch (error) {
    renderSummary({ success: false, error: error.message });
  }
};

const handleSongPics = async () => {
  if (!state.preciseResults.length) {
    renderSummary({ success: false, error: "您必须先搜索，才能获取歌曲封面" });
    return;
  }
  const payload = {
    songs: state.preciseResults.map((bundle) => ({
      id: bundle.song.id,
      display_id: bundle.song.display_id,
      search_source: bundle.lyric.search_source
    }))
  };
  try {
    const response = await window.api.getSongPics(payload);
    dom.consoleOutput.textContent = JSON.stringify(response.assets, null, 2);
    renderSummary(response.summary);
  } catch (error) {
    renderSummary({ success: false, error: error.message });
  }
};

const init = async () => {
  try {
    // 初始化时无需展示后端地址与版本号
  } catch (error) {
    console.error(error);
  }
};

dom.preciseForm.addEventListener("submit", handlePreciseSearch);
dom.exportLyrics.addEventListener("click", handleExport);
if (dom.fetchLinks) dom.fetchLinks.addEventListener("click", handleSongLinks);
if (dom.fetchPics) dom.fetchPics.addEventListener("click", handleSongPics);

init();
