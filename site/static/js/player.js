/**
 * 播放器控制 + 時間戳跳轉 + 即時字幕 + CEFR Tab 切換
 */

// --- 播放器切換 ---
function switchPlayer(mode) {
  var video = document.getElementById("video-player");
  var audio = document.getElementById("audio-player");
  var videoContainer = document.getElementById("video-container");
  var audioContainer = document.getElementById("audio-container");
  var buttons = document.querySelectorAll(".player-toggle");

  // 暫停兩個播放器
  if (video) video.pause();
  if (audio) audio.pause();

  // 同步播放進度
  if (mode === "video" && video && audio) {
    video.currentTime = audio.currentTime;
  }
  if (mode === "audio" && audio && video) {
    audio.currentTime = video.currentTime;
  }

  // 切換按鈕 active 狀態
  buttons.forEach(function (btn) {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });

  // 切換顯示
  if (mode === "video") {
    if (videoContainer) videoContainer.style.display = "";
    if (audioContainer) audioContainer.style.display = "none";
  } else {
    if (videoContainer) videoContainer.style.display = "none";
    if (audioContainer) audioContainer.style.display = "";
  }
}

// --- 時間戳工具 ---
function parseTimestamp(ts) {
  var parts = ts.split(":");
  if (parts.length === 2) {
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  }
  if (parts.length === 3) {
    return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseInt(parts[2], 10);
  }
  return 0;
}

function formatTime(seconds) {
  var m = Math.floor(seconds / 60);
  var s = Math.floor(seconds % 60);
  return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
}

// 跳轉到指定時間並播放
function seekTo(seconds) {
  var video = document.getElementById("video-player");
  var audio = document.getElementById("audio-player");
  var videoContainer = document.getElementById("video-container");
  var activePlayer = null;

  if (videoContainer && videoContainer.style.display !== "none") {
    activePlayer = video;
  } else {
    activePlayer = audio;
  }

  if (activePlayer) {
    activePlayer.currentTime = seconds;
    activePlayer.play();
  }
}

// --- 即時字幕 ---
var segments = [];
var lastSubtitleIdx = -1;

function findSegmentAt(time) {
  for (var i = 0; i < segments.length; i++) {
    if (time >= segments[i].startSec && time < segments[i].endSec) {
      return i;
    }
  }
  // 找最接近的（在兩段之間時顯示下一段）
  for (var j = 0; j < segments.length; j++) {
    if (time < segments[j].startSec) {
      return j > 0 ? j - 1 : -1;
    }
  }
  return segments.length > 0 ? segments.length - 1 : -1;
}

function updateSubtitle(time) {
  var idx = findSegmentAt(time);
  if (idx === lastSubtitleIdx) return;
  lastSubtitleIdx = idx;

  var timeEl = document.getElementById("subtitle-time");
  var deEl = document.getElementById("subtitle-de");
  var zhEl = document.getElementById("subtitle-zh");
  if (!timeEl) return;

  if (idx >= 0 && idx < segments.length) {
    var seg = segments[idx];
    timeEl.textContent = seg.start;
    deEl.innerHTML = seg.de + "<br><span class='subtitle-zh-line'>" + seg.zh + "</span>";
  } else {
    timeEl.textContent = "";
    deEl.innerHTML = "";
  }
}

function onTimeUpdate() {
  updateSubtitle(this.currentTime);
}

// --- CEFR Tab 切換 ---
function switchCefrTab(level) {
  var tabs = document.querySelectorAll(".cefr-tab");
  var contents = document.querySelectorAll(".cefr-content");

  tabs.forEach(function (tab) {
    tab.classList.toggle("active", tab.dataset.level === level);
  });
  contents.forEach(function (content) {
    content.classList.toggle("active", content.dataset.level === level);
  });
}

// --- 初始化 ---
document.addEventListener("DOMContentLoaded", function () {
  // 載入 segments 資料
  var dataEl = document.getElementById("segments-data");
  if (dataEl) {
    try {
      var raw = JSON.parse(dataEl.textContent);
      segments = raw.map(function (s) {
        return {
          start: s.start,
          startSec: parseTimestamp(s.start),
          endSec: s.end ? parseTimestamp(s.end) : parseTimestamp(s.start) + 30,
          de: s.de || "",
          zh: s.zh || ""
        };
      });
    } catch (e) {
      console.warn("字幕資料載入失敗:", e);
    }
  }

  // 綁定 timeupdate 事件
  var video = document.getElementById("video-player");
  var audio = document.getElementById("audio-player");
  if (video) video.addEventListener("timeupdate", onTimeUpdate);
  if (audio) audio.addEventListener("timeupdate", onTimeUpdate);

  // 綁定時間戳點擊
  var timestamps = document.querySelectorAll(".ts-link");
  timestamps.forEach(function (el) {
    el.style.cursor = "pointer";
    el.addEventListener("click", function () {
      var time = this.dataset.time || this.textContent;
      seekTo(parseTimestamp(time));
    });
  });

  // 綁定 CEFR tab 點擊
  var cefrTabs = document.querySelectorAll(".cefr-tab");
  cefrTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      switchCefrTab(this.dataset.level);
    });
  });

  // 字幕列 sticky 偵測
  var subtitleBar = document.getElementById("subtitle-bar");
  var mediaPlayer = document.getElementById("media-player");
  if (subtitleBar && mediaPlayer) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        subtitleBar.classList.toggle("sticky", !entry.isIntersecting);
      });
    }, { threshold: 0 });
    observer.observe(mediaPlayer);
  }
});
