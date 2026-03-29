"""解析 Tagesschau 20 Uhr Podcast RSS feed，取得最新一集的 metadata 並下載 MP3。"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests

import config

logger = logging.getLogger(__name__)

# 德國時區 CET/CEST
CET = timezone(timedelta(hours=1))


def parse_feed(url: str) -> feedparser.FeedParserDict:
    """解析 RSS feed，回傳 feedparser 結果。"""
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"RSS 解析失敗：{feed.bozo_exception}")
    return feed


def get_latest_episode(feed: feedparser.FeedParserDict) -> dict:
    """從 feed 取出最新一集的 metadata。"""
    if not feed.entries:
        raise RuntimeError("RSS feed 沒有任何集數")
    return parse_entry(feed.entries[0])


def is_target_date(pub_dt: datetime, target: datetime.date = None) -> bool:
    """檢查 pub_date 是否為目標日期（預設今天，CET 時區）。"""
    if pub_dt is None:
        return False
    if target is None:
        target = datetime.now(CET).date()
    return pub_dt.date() == target


def download_mp3(url: str, output_dir: Path) -> Path:
    """下載 MP3 到指定目錄，回傳本地檔案路徑。"""
    filename = url.split("/")[-1]
    filepath = output_dir / filename
    logger.info(f"下載 MP3：{url}")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.info(f"MP3 已儲存：{filepath}（{filepath.stat().st_size / 1024 / 1024:.1f} MB）")
    return filepath


def find_episode_by_date(feed: feedparser.FeedParserDict, target: datetime.date) -> dict | None:
    """從 feed 中找出指定日期的集數。"""
    for entry in feed.entries:
        pub_struct = entry.get("published_parsed")
        if pub_struct:
            pub_dt = datetime(*pub_struct[:6], tzinfo=CET)
            if pub_dt.date() == target:
                return parse_entry(entry)
    return None


def parse_entry(entry) -> dict:
    """將 feedparser entry 轉為 metadata dict。"""
    pub_struct = entry.get("published_parsed")
    pub_dt = datetime(*pub_struct[:6], tzinfo=CET) if pub_struct else None

    enclosure_url = ""
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure":
            enclosure_url = link.get("href", "")
            break
    if not enclosure_url and hasattr(entry, "enclosures") and entry.enclosures:
        enc = entry.enclosures[0]
        enclosure_url = enc.get("href", enc.get("url", ""))

    return {
        "title": entry.get("title", ""),
        "pub_date": pub_dt,
        "description": entry.get("summary", entry.get("description", "")),
        "enclosure_url": enclosure_url,
        "duration": entry.get("itunes_duration", ""),
        "guid": entry.get("id", ""),
        "link": entry.get("link", ""),
    }


def fetch_podcast() -> dict:
    """主函式：取得 Podcast metadata 並下載 MP3。

    含重試機制：若最新集不是目標日期的，等待後重試。

    環境變數：
        TARGET_DATE=YYYY-MM-DD  指定日期（補跑用），從 RSS 歷史中搜尋
        SKIP_DATE_CHECK=1       跳過日期檢查，直接用最新集數（測試用）

    回傳 dict 包含：
        title, pub_date, description, audio_url, video_url,
        duration, guid, mp3_path, topics
    """
    skip_date = os.getenv("SKIP_DATE_CHECK", "") == "1"
    target_date_str = os.getenv("TARGET_DATE", "")

    # 解析目標日期
    target_date = None
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        logger.info(f"指定目標日期：{target_date}")

    for attempt in range(1, config.MAX_RETRIES + 1):
        logger.info(f"嘗試取得 Podcast（第 {attempt}/{config.MAX_RETRIES} 次）")

        audio_feed = parse_feed(config.AUDIO_RSS_URL)
        video_feed = parse_feed(config.VIDEO_RSS_URL)

        # 指定日期模式：從歷史中搜尋
        if target_date:
            audio_ep = find_episode_by_date(audio_feed, target_date)
            video_ep = find_episode_by_date(video_feed, target_date)
            if audio_ep and video_ep:
                logger.info(f"找到 {target_date} 的集數：{audio_ep['title']}")
                break
            if attempt < config.MAX_RETRIES:
                logger.warning(
                    f"RSS 中找不到 {target_date} 的集數，"
                    f"{config.RETRY_INTERVAL_SEC} 秒後重試..."
                )
                time.sleep(config.RETRY_INTERVAL_SEC)
                continue
            raise RuntimeError(f"RSS 中找不到 {target_date} 的音訊或影片集數")

        audio_ep = get_latest_episode(audio_feed)
        video_ep = get_latest_episode(video_feed)

        if skip_date:
            logger.info(f"跳過日期檢查，使用最新集數：{audio_ep['title']}")
            break

        if is_target_date(audio_ep["pub_date"]):
            logger.info(f"找到今天的集數：{audio_ep['title']}")
            break

        if attempt < config.MAX_RETRIES:
            logger.warning(
                f"最新集日期 {audio_ep['pub_date']} 不是今天，"
                f"{config.RETRY_INTERVAL_SEC} 秒後重試..."
            )
            time.sleep(config.RETRY_INTERVAL_SEC)
    else:
        # 所有重試都失敗，仍使用最新的一集
        logger.warning("重試次數已用完，使用最新可用的集數")

    # 下載 MP3
    mp3_path = download_mp3(audio_ep["enclosure_url"], config.OUTPUT_DIR)

    # 從 description 擷取主題列表（逗號分隔）
    desc = audio_ep["description"]
    topics = [t.strip() for t in desc.split(",") if t.strip()]
    # 移除「Das Wetter」、Hinweis、換行開頭的項目
    topics = [
        t for t in topics
        if not t.startswith("Hinweis")
        and not t.startswith("\n")
        and not t.startswith("Das Wetter")
    ]

    return {
        "title": audio_ep["title"],
        "pub_date": audio_ep["pub_date"],
        "description": audio_ep["description"],
        "audio_url": audio_ep["enclosure_url"],
        "video_url": video_ep["enclosure_url"],
        "duration": audio_ep["duration"],
        "guid": audio_ep["guid"],
        "link": audio_ep["link"],
        "mp3_path": mp3_path,
        "topics": topics,
    }
