from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from redis import Redis

from app.core.config import settings
from app.db.models import AnalysisRequest, AnalysisStatus, BotSettings, GeneratedReport, Lead, SelectedProblem, TelegramUser
from app.db.session import SessionLocal
from app.storage.local import local_storage
from app.workers.tasks_analysis import run_analysis_pipeline


DONE_STATUSES = {AnalysisStatus.COMPLETED, AnalysisStatus.NEEDS_REVIEW, AnalysisStatus.FAILED, AnalysisStatus.FAILED_PROTOCOL_RENDER}
SUCCESS_STATUSES = {AnalysisStatus.COMPLETED, AnalysisStatus.NEEDS_REVIEW}


def _source_photo() -> str:
    relative = "load_tests/mock_source.jpg"
    target = Path(local_storage.abs_path(relative))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return relative

    image = Image.new("RGB", (900, 1200), "#eaded5")
    draw = ImageDraw.Draw(image)
    draw.ellipse((265, 185, 635, 650), fill="#d7a58b", outline="#8d5f50", width=4)
    draw.ellipse((348, 360, 408, 420), fill="#3a2a1e")
    draw.ellipse((492, 360, 552, 420), fill="#3a2a1e")
    draw.arc((370, 450, 530, 560), 20, 160, fill="#8d5f50", width=4)
    draw.arc((372, 520, 528, 610), 20, 160, fill="#7f3c38", width=5)
    draw.rounded_rectangle((315, 700, 585, 1180), radius=80, fill="#f7f0e3")
    draw.text((290, 90), "LOAD TEST MOCK PHOTO", fill="#3a2a1e")
    image.save(target, quality=88)
    return relative


def _queue_len(queue: str) -> int:
    if not settings.redis_url:
        return 0
    client = Redis.from_url(settings.redis_url)
    try:
        return int(client.llen(queue))
    finally:
        client.close()


def _status_counts(db, ids: list[int]) -> dict[str, int]:
    rows = db.query(AnalysisRequest.status).filter(AnalysisRequest.id.in_(ids)).all()
    counts: dict[str, int] = {}
    for (status,) in rows:
        counts[status] = counts.get(status, 0) + 1
    return counts


def _create_batch(count: int, batch_id: str) -> list[int]:
    db = SessionLocal()
    try:
        photo_path = _source_photo()
        selected = ["Зона глаз", "Овал лица", "Лимфоток"]
        ids: list[int] = []
        base_telegram_id = 8_800_000_000_000 + int(time.time()) % 100_000 * 10_000
        for index in range(count):
            telegram_user = TelegramUser(
                telegram_id=base_telegram_id + index,
                username=f"{batch_id}_{index}",
                first_name="Load",
                last_name="Test",
                current_status=AnalysisStatus.QUEUED,
                start_payload=batch_id,
            )
            lead = Lead(
                telegram_user=telegram_user,
                name=f"LoadTest {index + 1}",
                status=AnalysisStatus.QUEUED,
                selected_problems=selected,
                source=batch_id,
                tags=["load_test", batch_id],
            )
            analysis = AnalysisRequest(
                telegram_user=telegram_user,
                lead=lead,
                status=AnalysisStatus.QUEUED,
                selected_problems=selected,
                original_photo_path=photo_path,
                analysis_json={},
                report_json={},
                protocol_copy_json={},
                personal_insight_json={},
                protocol_slide_paths=[],
                protocol_slide_copy={},
                after_photo_plan={},
                after_photo_variants=[],
                after_photo_variant_paths=[],
                after_photo_quality_results=[],
            )
            db.add(analysis)
            db.flush()
            for problem in selected:
                db.add(SelectedProblem(analysis_id=analysis.id, slug=problem, title=problem))
            ids.append(analysis.id)
            if len(ids) % 50 == 0:
                db.commit()
                print(json.dumps({"event": "created", "count": len(ids)}, ensure_ascii=False), flush=True)
        db.commit()
        return ids
    finally:
        db.close()


def _enqueue(ids: list[int], queue: str) -> None:
    for index, analysis_id in enumerate(ids, start=1):
        run_analysis_pipeline.apply_async(args=[analysis_id], queue=queue)
        if index % 50 == 0:
            print(json.dumps({"event": "enqueued", "count": index, "queue": queue}, ensure_ascii=False), flush=True)


def run(count: int, queue: str, timeout_seconds: int, poll_seconds: int) -> int:
    batch_id = f"loadtest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    db = SessionLocal()
    settings_row = db.query(BotSettings).first()
    if not settings_row:
        raise RuntimeError("BotSettings row not found")
    previous_manual_moderation = bool(settings_row.manual_moderation_enabled)
    settings_row.manual_moderation_enabled = True
    db.commit()
    db.close()

    started_at = time.monotonic()
    ids: list[int] = []
    try:
        print(
            json.dumps(
                {
                    "event": "load_test_started",
                    "batch_id": batch_id,
                    "count": count,
                    "queue": queue,
                    "manual_moderation_enabled": True,
                    "openai_safe": "requires mock worker with AI_FORCE_MOCK=true",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        ids = _create_batch(count, batch_id)
        _enqueue(ids, queue)

        while True:
            db = SessionLocal()
            try:
                counts = _status_counts(db, ids)
                done = sum(counts.get(status, 0) for status in DONE_STATUSES)
                failed = counts.get(AnalysisStatus.FAILED, 0) + counts.get(AnalysisStatus.FAILED_PROTOCOL_RENDER, 0)
                reports = db.query(GeneratedReport).filter(GeneratedReport.analysis_id.in_(ids)).count()
                pngs = db.query(AnalysisRequest).filter(AnalysisRequest.id.in_(ids), AnalysisRequest.face_protocol_image_path.isnot(None)).count()
            finally:
                db.close()

            elapsed = time.monotonic() - started_at
            print(
                json.dumps(
                    {
                        "event": "progress",
                        "elapsed_sec": round(elapsed, 1),
                        "done": done,
                        "failed": failed,
                        "reports": reports,
                        "pngs": pngs,
                        "queue_len": _queue_len(queue),
                        "statuses": counts,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            if done >= count:
                break
            if elapsed > timeout_seconds:
                print(json.dumps({"event": "timeout", "elapsed_sec": round(elapsed, 1)}, ensure_ascii=False), flush=True)
                return 2
            time.sleep(poll_seconds)

        elapsed = time.monotonic() - started_at
        success = sum(counts.get(status, 0) for status in SUCCESS_STATUSES)
        result = {
            "event": "load_test_finished",
            "batch_id": batch_id,
            "count": count,
            "success": success,
            "failed": failed,
            "elapsed_sec": round(elapsed, 1),
            "avg_sec_per_request": round(elapsed / max(count, 1), 3),
            "reports": reports,
            "pngs": pngs,
            "statuses": counts,
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0 if failed == 0 and success == count else 1
    finally:
        db = SessionLocal()
        try:
            settings_row = db.query(BotSettings).first()
            if settings_row:
                settings_row.manual_moderation_enabled = previous_manual_moderation
                db.commit()
        finally:
            db.close()
        print(
            json.dumps(
                {
                    "event": "settings_restored",
                    "manual_moderation_enabled": previous_manual_moderation,
                    "created_ids": len(ids),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--queue", default="load_test_analysis")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(run(args.count, args.queue, args.timeout_seconds, args.poll_seconds))


if __name__ == "__main__":
    main()
