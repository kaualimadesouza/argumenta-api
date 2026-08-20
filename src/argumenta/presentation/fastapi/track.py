import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from argumenta.application.gameplay.ports import DraftRepository
from argumenta.application.track.ports import (
    ActivityRepository,
    ContentRepository,
    ProgressRepository,
)
from argumenta.application.track.use_cases import GetChapterUseCase, GetTrackUseCase
from argumenta.domain.enums import BeatType, Branch, ChapterKind, ChapterStatus
from argumenta.domain.track import StoryState
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_activity_repository,
    get_content_repository,
    get_draft_repository,
    get_progress_repository,
)

router = APIRouter(tags=["track"])

Content = Annotated[ContentRepository, Depends(get_content_repository)]
Progress = Annotated[ProgressRepository, Depends(get_progress_repository)]
Activity = Annotated[ActivityRepository, Depends(get_activity_repository)]
Drafts = Annotated[DraftRepository, Depends(get_draft_repository)]


class TrackStoryResponse(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    synopsis: str
    position: int
    is_tutorial: bool
    cover_asset: str | None
    state: StoryState
    chapters_passed: int
    chapters_total: int


class TrackResponse(BaseModel):
    stories: list[TrackStoryResponse]
    streak_days: int
    submissions_today: int
    daily_limit: int


class BeatResponse(BaseModel):
    beat_type: BeatType
    body: str
    character_name: str | None
    character_portrait: str | None
    illustration_asset: str | None


class ChapterResponse(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    position: int
    kind: ChapterKind
    title: str
    objective: str
    min_words: int
    max_words: int
    antagonist_name: str
    antagonist_portrait: str | None
    status: ChapterStatus
    branch: Branch
    draft_body: str | None
    beats: list[BeatResponse]


@router.get("/track")
def get_track(
    user_id: CurrentUserId, content: Content, progress: Progress, activity: Activity
) -> TrackResponse:
    view = GetTrackUseCase(content, progress, activity).execute(user_id)
    return TrackResponse(
        stories=[
            TrackStoryResponse(
                id=item.story.id,
                slug=item.story.slug,
                title=item.story.title,
                synopsis=item.story.synopsis,
                position=item.story.position,
                is_tutorial=item.story.is_tutorial,
                cover_asset=item.story.cover_asset,
                state=item.state,
                chapters_passed=item.chapters_passed,
                chapters_total=item.chapters_total,
            )
            for item in view.stories
        ],
        streak_days=view.streak_days,
        submissions_today=view.submissions_today,
        daily_limit=view.daily_limit,
    )


@router.get("/chapters/{chapter_id}")
def get_chapter(
    chapter_id: uuid.UUID,
    user_id: CurrentUserId,
    content: Content,
    progress: Progress,
    drafts: Drafts,
) -> ChapterResponse:
    script = GetChapterUseCase(content, progress).execute(user_id, chapter_id)
    return ChapterResponse(
        id=script.chapter.id,
        story_id=script.chapter.story_id,
        position=script.chapter.position,
        kind=script.chapter.kind,
        title=script.chapter.title,
        objective=script.chapter.objective,
        min_words=script.chapter.min_words,
        max_words=script.chapter.max_words,
        antagonist_name=script.chapter.antagonist_name,
        antagonist_portrait=script.chapter.antagonist_portrait,
        status=script.status,
        branch=script.branch,
        draft_body=drafts.get(user_id, chapter_id),
        beats=[
            BeatResponse(
                beat_type=beat.beat_type,
                body=beat.body,
                character_name=beat.character_name,
                character_portrait=beat.character_portrait,
                illustration_asset=beat.illustration_asset,
            )
            for beat in script.beats
        ],
    )
