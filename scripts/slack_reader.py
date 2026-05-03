"""Reads messages from Slack channels via the Slack Web API."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


WORKSPACES = {
    "llm-d": {
        "token_env": "SLACK_TOKEN_LLMD",
        "channels": ["sig-autoscaling", "sig-benchmarking"],
    },
    "kubernetes": {
        "token_env": "SLACK_TOKEN_K8S",
        "channels": ["sig-network-multi-network"],
    },
}


class SlackReader:
    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self._channel_cache: dict[str, str] = {}

    def _resolve_channel_id(self, channel_name: str) -> str | None:
        if channel_name in self._channel_cache:
            return self._channel_cache[channel_name]

        cursor = None
        while True:
            resp = self.client.conversations_list(
                types="public_channel,private_channel",
                limit=200,
                cursor=cursor,
            )
            for ch in resp["channels"]:
                if ch["name"] == channel_name:
                    self._channel_cache[channel_name] = ch["id"]
                    return ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return None

    def _resolve_usernames(self, user_ids: set[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for uid in user_ids:
            try:
                resp = self.client.users_info(user=uid)
                profile = resp["user"].get("profile", {})
                result[uid] = profile.get("display_name") or profile.get("real_name") or uid
            except SlackApiError:
                result[uid] = uid
        return result

    def read_channel(
        self,
        channel_name: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        channel_id = self._resolve_channel_id(channel_name)
        if not channel_id:
            print(f"[SlackReader] Channel not found: {channel_name}")
            return []

        now = datetime.now(tz=timezone.utc)
        oldest = (now - timedelta(hours=hours)).timestamp()

        messages: list[dict[str, Any]] = []
        cursor = None

        while True:
            try:
                resp = self.client.conversations_history(
                    channel=channel_id,
                    oldest=str(oldest),
                    limit=200,
                    cursor=cursor,
                )
            except SlackApiError as e:
                print(f"[SlackReader] Error reading {channel_name}: {e}")
                break

            raw_messages = resp.get("messages", [])
            for msg in raw_messages:
                if msg.get("type") != "message" or msg.get("subtype"):
                    continue
                messages.append(msg)

            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.5)

        # Resolve replies for threads
        threaded: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("reply_count", 0) > 0:
                try:
                    resp = self.client.conversations_replies(
                        channel=channel_id,
                        ts=msg["ts"],
                        oldest=str(oldest),
                    )
                    msg["replies"] = resp.get("messages", [])[1:]  # exclude parent
                except SlackApiError:
                    msg["replies"] = []
            threaded.append(msg)

        # Resolve user IDs to names
        user_ids: set[str] = set()
        for msg in threaded:
            if "user" in msg:
                user_ids.add(msg["user"])
            for reply in msg.get("replies", []):
                if "user" in reply:
                    user_ids.add(reply["user"])
        usernames = self._resolve_usernames(user_ids)

        # Build structured output
        result: list[dict[str, Any]] = []
        for msg in threaded:
            ts = float(msg["ts"])
            entry: dict[str, Any] = {
                "ts": msg["ts"],
                "datetime": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                "user_id": msg.get("user", ""),
                "user_name": usernames.get(msg.get("user", ""), ""),
                "text": msg.get("text", ""),
                "channel": channel_name,
                "replies": [
                    {
                        "ts": r["ts"],
                        "datetime": datetime.fromtimestamp(float(r["ts"]), tz=timezone.utc).isoformat(),
                        "user_id": r.get("user", ""),
                        "user_name": usernames.get(r.get("user", ""), ""),
                        "text": r.get("text", ""),
                    }
                    for r in msg.get("replies", [])
                ],
            }
            result.append(entry)

        return result
