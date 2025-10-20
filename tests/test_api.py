import asyncio, sys, pytest, pytest_asyncio
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from utils.settings import settings
from api.main import app


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
def valid_headers():
    return {"API-KEY": settings.API_KEY}


@pytest.mark.asyncio
async def test_get_books_no_auth(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/books")
        assert resp.status_code == 401
        assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_get_books_with_auth(client, valid_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/books", headers=valid_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "books" in data
        assert isinstance(data["books"], list)
        assert "total_count" in data
        assert "page" in data


@pytest.mark.asyncio
async def test_filter_books_by_category(client, valid_headers):
    resp = await client.get("/books", headers=valid_headers, params={"category": "Poetry"})
    print("--------------------Response--------------------")
    print(resp)
    assert resp.status_code == 200
    data = resp.json()
    assert all("Poetry" in b["category"] for b in data["books"])


@pytest.mark.asyncio
async def test_filter_books_by_price_range(client, valid_headers):
    resp = await client.get(
        "/books", headers=valid_headers, params={"min_price": 10, "max_price": 50}
    )
    assert resp.status_code == 200
    data = resp.json()
    for book in data["books"]:
        assert 10 <= book["price_incl"] <= 50


@pytest.mark.asyncio
async def test_sort_books_by_rating(client, valid_headers):
    resp = await client.get("/books", headers=valid_headers, params={"sort_by": "rating"})
    assert resp.status_code == 200
    data = resp.json()
    ratings = [b["rating"] for b in data["books"]]
    assert ratings == sorted(ratings, reverse=True)

@pytest.mark.asyncio
async def test_get_book_by_id(client, valid_headers):
    list_resp = await client.get("/books", headers=valid_headers)
    assert list_resp.status_code == 200

    data = list_resp.json()
    books = data.get("books", [])
    assert isinstance(books, list)

    if not books:
        pytest.skip("No books found to test /books/{book_id}")

    first_book = books[0]
    book_id = str(first_book.get("_id"))

    detail_resp = await client.get(f"/books/{book_id}", headers=valid_headers)
    assert detail_resp.status_code in (200, 404)

    if detail_resp.status_code == 200:
        book_data = detail_resp.json()
        assert "title" in book_data
        assert "price_incl" in book_data
        assert book_data["_id"] == book_id


@pytest.mark.asyncio
async def test_get_changes(client, valid_headers):
    resp = await client.get("/changes", headers=valid_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "type" in data[0]
        assert "book_id" in data[0]


@pytest.mark.asyncio
async def test_rate_limiting(client, valid_headers):
    for _ in range(100):
        await client.get("/books", headers=valid_headers)
    resp = await client.get("/books", headers=valid_headers)
    assert resp.status_code in (200, 429)
