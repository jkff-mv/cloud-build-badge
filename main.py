#!/usr/bin/env python3

"""Cloud Build Badge

Cloud Buildの情報からバッジを生成し、GCSへ保存する。
GCSのバケットは予め作成し、環境変数 ``_CLOUD_BUILD_BADGE_BUCKET`` にバケット名を設定しておくこと。

"""

__version__ = "0.3.0"

import base64
from collections import defaultdict
import dataclasses
import json
import logging
import os
import sys
from typing import List, Optional, overload

from google.cloud import storage
import pybadges


@dataclasses.dataclass(frozen=True)
class Build:
    """ビルドの情報。

    Parameters
    ----------
    status : str
        ステータス。
    trigger : str
        トリガID。
    repository : str, optional
        リポジトリ名。
    branch : str, optional
        ブランチ名。

    """

    status: str
    trigger: str
    repository: Optional[str] = None
    branch: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Badge:
    """バッジオブジェクト。

    Parameters
    ----------
    label : str
        ラベル。
    message : str
        メッセージ。
    color : str
        16進数カラーコード。
    logo : str, optional
        Data URI形式のロゴ画像。

    """

    label: str
    message: str
    color: str
    logo: Optional[str] = None

    def to_svg(self) -> str:
        """SVG形式のバッジを生成する。

        Returns
        -------
        str
            SVG形式の画像データ。

        """

        return pybadges.badge(
            logo=self.logo,
            left_text=self.label,
            right_text=self.message,
            right_color=self.color,
        )


def entry_point(event, context):
    """エントリポイント。"""

    try:
        return run(event, context)
    except Exception as e:
        logging.error(e)
        sys.exit(1)


def run(event, context):
    """メイン処理。"""

    # Pub/Subのメッセージを取得する。
    pubsub_msg = base64.b64decode(event["data"]).decode("utf-8")
    pubsub_msg_dict = json.loads(pubsub_msg)

    # 関係ないステータスの場合は抜ける。
    build = parse_build_info(pubsub_msg_dict)
    if build.status not in {
        "WORKING",
        "SUCCESS",
        "FAILURE",
        "CANCELLED",
        "TIMEOUT",
        "FAILED",
    }:
        return

    # 設定でバッジの生成が無効化されている場合は抜ける。
    badge_generation_setting = get_setting(
        "_CLOUD_BUILD_BADGE_GENERATION", pubsub_msg_dict, default="enabled"
    )
    if badge_generation_setting == "disabled":
        logging.info("The badge generation setting is disabled.")
        return

    # 保存先のGCSバケットが設定されていることを確認する。
    bucket_name = get_setting("_CLOUD_BUILD_BADGE_BUCKET", pubsub_msg_dict)
    if not bucket_name:
        raise RuntimeError(
            "Bucket name is not set. "
            "Set the value to the environment variable '_CLOUD_BUILD_BADGE_BUCKET'."
        )

    if not build.repository:
        logging.info("Unknown repository.")
    if not build.branch:
        logging.info("Unknown branch.")

    # バッジを生成し、GCSへ保存する。
    badge = create_badge(pubsub_msg_dict)
    uploaded_badges = upload_badge_to_gcs(badge, bucket_name, build)

    for url in uploaded_badges:
        logging.info(f"Uploaded the badge to '{url}'.")


def parse_build_info(msg: dict) -> Build:
    """Cloud Buildの情報から必要なデータを取り出す。

    Parameters
    ----------
    msg : dict
        Pub/Subから受け取ったメッセージ。

    Returns
    -------
    Build
        Pub/Subのメッセージをパースしたデータ。

    """

    status = msg["status"]
    trigger = msg["buildTriggerId"]

    # ビルドの定義ファイル自体が壊れていた場合など、情報が取得できないことがある。
    repository, branch = None, None
    if "substitutions" in msg:
        repository = msg["substitutions"].get("REPO_NAME")
        branch = msg["substitutions"].get("BRANCH_NAME")

    return Build(
        status=status, trigger=trigger, repository=repository, branch=branch
    )


def create_badge(msg: dict) -> Badge:
    """バッジを生成する。

    Parameters
    ----------
    msg : dict
        Pub/Subから受け取ったメッセージ。

    Returns
    -------
    Badge
        ビルドのステータスを示すバッジ。

    """

    status = msg["status"]
    label = get_setting("_CLOUD_BUILD_BADGE_LABEL", msg, default="build")
    logo = get_setting("_CLOUD_BUILD_BADGE_LOGO", msg)

    status_to_color = defaultdict(lambda: "#9f9f9f")
    status_to_color["WORKING"] = "#dfb317"
    status_to_color["SUCCESS"] = "#44cc11"
    status_to_color["FAILURE"] = "#e05d44"

    return Badge(
        label=label,
        message=status.lower(),
        color=status_to_color[status],
        logo=logo,
    )


def upload_badge_to_gcs(
    badge: Badge, bucket_name: str, build: Build
) -> List[str]:
    """バッジをGCSに保存する。

    Parameters
    ----------
    badge : Badge
        バッジ。
    bucket_name : str
        バケット名。
    build : Build
        ビルドの情報。

    Returns
    -------
    list of str
        GCSに保存したバッジのURLを格納したリスト。

    """

    def upload(path: str) -> None:
        bucket = gcs_client.get_bucket(bucket_name)
        blob = bucket.blob(path)
        blob.cache_control = "max-age=60, s-maxage=60"
        blob.upload_from_string(badge.to_svg(), content_type="image/svg+xml")

    def to_url(path: str) -> str:
        return f"https://storage.googleapis.com/{bucket_name}/{path}"

    uploaded = []

    gcs_client = storage.Client()

    path = f"triggers/{build.trigger}/badge.svg"
    upload(path)
    uploaded.append(to_url(path))

    if not build.repository or not build.branch:
        return uploaded

    branch = build.branch.replace("/", "_")  # スラッシュは使えないので置換する。
    path = f"repositories/{build.repository}/triggers/{build.trigger}/branches/{branch}/badge.svg"
    upload(path)
    uploaded.append(to_url(path))

    return uploaded


@overload
def get_setting(key: str, msg: dict) -> Optional[str]:
    ...


@overload
def get_setting(key: str, msg: dict, default: None) -> Optional[str]:
    ...


@overload
def get_setting(key: str, msg: dict, default: str) -> str:
    ...


def get_setting(key, msg, default=None):
    """設定値を取得する。

    Parameters
    ----------
    key : str
        設定値取得のためのキー。
    msg : dict
        Pub/Subから受け取ったメッセージ。
    default : str, optional
        設定値が存在しなかった際のデフォルト値。

    Returns
    -------
    str or None
        設定値（存在しない場合は `None` もしくは `default` に指定した値）。

    """

    value = None

    if "substitutions" in msg:
        value = msg["substitutions"].get(key)
    if not value:
        value = os.getenv(key)
    if not value:
        value = default

    return None if value is None else str(value)
