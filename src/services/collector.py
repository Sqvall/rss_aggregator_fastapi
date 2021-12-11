import logging
from typing import Optional, List

import feedparser as fp
import httpx

from celery_app.tasks import example_task
from db.database import async_session
from db.repositories.entries import EntriesRepository
from db.repositories.feeds import FeedsRepository
from models import Entry
from services.errors import CollectFeedDataError

logger = logging.getLogger(__name__)


async def fetch_feed_data(*, client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        response = await client.get(url)
    except httpx.RequestError as exc:
        error_message = f"An error occurred while requesting {exc.request.url!r}."
        logger.warning(error_message)
        return None

    return response.text


async def parse_feeds(*, feed_id: int = None):
    async with async_session() as session:
        feed_repo = FeedsRepository(session)

        if feed_id:
            feeds = [await feed_repo.get_by_id(id_=feed_id)]
        else:
            feeds = await feed_repo.list_feeds(limit=None)

        for feed in feeds:

            if not feed.can_updated:
                continue

            async with httpx.AsyncClient() as client:
                xml = await fetch_feed_data(client=client, url=feed.source_url)

                if xml is None:
                    continue

            parse_data = fp.parse(xml)

            if parse_data.bozo:  # not valid xml or failure response
                error_message = f"Not valid xml or failure response when trying collect entries " \
                                f"for Feed (id: {feed.id})."
                logger.warning(error_message)
                raise CollectFeedDataError(error_message)

            feed_resp = parse_data['channel']

            await feed_repo.update(
                feed_id=feed.id,
                title=feed_resp.get('title'),
                description=feed_resp.get('subtitle'),
            )

            entries = []

            for i in parse_data['items']:
                entries.append(Entry(link=i['url'], feed_id=feed.id, title=i['title']))

            await EntriesRepository(session).add_all(entries)

        await session.commit()
