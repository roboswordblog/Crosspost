import os
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from datamanagement import get_auth_tokens, update_auth_tokens


YOUTUBE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _credentials_to_dict(credentials: Credentials) -> dict:
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def _build_credentials_from_tokens(tokens: dict) -> Optional[Credentials]:
    required = {"token", "refresh_token", "token_uri", "client_id", "client_secret"}
    if not tokens or not required.issubset(tokens.keys()):
        return None
    return Credentials(
        token=tokens.get("token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens.get("token_uri"),
        client_id=tokens.get("client_id"),
        client_secret=tokens.get("client_secret"),
        scopes=tokens.get("scopes") or YOUTUBE_UPLOAD_SCOPES,
    )


def publish_to_youtube(username, video_path, title, description="", tags=None, privacy_status="private"):
    if not username:
        raise ValueError("Username is required.")
    if not video_path or not os.path.isfile(video_path):
        raise ValueError("A valid video file path is required.")
    if not title or not str(title).strip():
        raise ValueError("Video title is required.")

    stored_tokens = get_auth_tokens(username) or {}
    youtube_tokens = stored_tokens.get("youtube") if isinstance(stored_tokens, dict) else None
    credentials = _build_credentials_from_tokens(youtube_tokens)
    if not credentials:
        raise ValueError("No YouTube OAuth tokens found for this user.")

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        merged_tokens = stored_tokens if isinstance(stored_tokens, dict) else {}
        merged_tokens["youtube"] = _credentials_to_dict(credentials)
        update_auth_tokens(username, merged_tokens)

    youtube = build("youtube", "v3", credentials=credentials)
    request_body = {
        "snippet": {
            "title": str(title).strip(),
            "description": str(description or ""),
            "tags": tags or [],
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    media = MediaFileUpload(video_path, resumable=True)
    insert_request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )
    response = insert_request.execute()
    return response
