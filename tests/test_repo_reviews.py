import asyncio
from app.repo import create_master, create_service, create_review, list_reviews, average_rating_for_master, average_rating_for_service


def test_create_and_list_reviews(temp_db):
    async def _run():
        mid = await create_master('M1','b','c')
        sid = await create_service('S1','d',10.0,30)
        # create reviews
        r1 = await create_review(1, sid, None, 5, 'Great')
        r2 = await create_review(1, sid, mid, 4, 'Good')
        rows = await list_reviews(service_id=sid)
        assert any(r['id'] == r1 for r in rows)
        assert any(r['id'] == r2 for r in rows)
        avg, cnt = await average_rating_for_service(sid)
        assert cnt >= 2
        assert avg >= 4.0
        avgm, cntm = await average_rating_for_master(mid)
        assert cntm >= 1
    asyncio.run(_run())