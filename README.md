# Book Website Crawler.
This repository aims at crawling https://books.toscrape.com and scraping data to MongoDB, then run scheduler to check change status. There is also an API to get books and changes' data.<br/><br/>

**This project has 4 parts-**
- **Crawler**<br/>
It runs the crawler method with asyncio which uses **httpx** to load website data, parse them with **BeautifulSoup** and save them to **MongoDB** with **motor**.<br/>
In case of failure it resumes from where it had finished.<br/>
It does so by keeping a track of the latest page that was being crawled.
- **Scheduler**<br/>
It uses **APScheduler** to run everyday at a particular time mentioned in **.env** file.<br/>
It checks for new entries and changes and save them accordingly.<br/>
It uses the same **httpx**, **BeautifulSoup** and **motor** to load, parse and save data to the database.<br/>
You can optionally export the changes report to json files.
- **API**<br/>
It uses **FastAPI** to serve **books** and **changes** data to users.<br/>
It uses **slowapi** with **Redis** for rate limiting, **motor** for serving book and changes' data.<br/>
The endpoints are protected with **API Key**.<br/>
The API endpoints can be served with **uvicorn** or any other ASGI server.
- **Tests**<br/>
Uses **pytest** to test the API endpoints.

## Requirements
- Python 3.11+
- MongoDB 8.0+
- Redis 7.2+

The rest of the dependencies are mentioned in **requirements.txt** and can be installed through **pip**.

## Getting started
Clone the repository from [GitHub](https://github.com/HqShiblu/Book-Website-Crawler).

Create a virtual environment.
Use **python** in **Windows** and **python3** in **Linux**.
```
python -m venv book_crawler_env
```

Move to **Scripts** (in **Windows**) or **bin** (in **Linux**) folder of the environment.<br/>
Then activate the environment<br/>
in Windows with
```
activate
```

or in Linux with
```
source activate
```

Then, move to the location of the project where **.env.example** file is.
Install the required packages with 
```
pip install -r requirements.txt
```
Use **pip** in **Windows** and **pip3** in **Linux**.

Open the **.env.example** file.<br/>
Change or assign the values accordingly and save it as **.env** file in the same folder.


### Run the Crawler
Move to the project root folder and run the crawler with
```
python -m crawler.main
```

Use **python3** in Linux.

### Run the Scheduler
Move to the project root folder and run the scheduler with
```
python -m scheduler.main
```

Use **python3** in Linux.<br/>
The scheduler will run in the time mentioned in **.env** file.

### Run the API Server
Move to the project root folder.
Suppose you want to run the API server in port 8000 of your localhost.
You can do so with
```
uvicorn api.main:app --host localhost --port 8000
```
### Run the Tests
Move to the project root folder and run the tests with
```
pytest -v tests/test_api.py
```

## API Endpoints
The API Endpoints are protected.<br/>
You need to assign an API Key in header.
It also limits how frequent you can access the endpoints
The values are taken from **.env** file.<br/>
You can check the **Swagger UI** in ``GET /docs``.

#### **1.** ` GET /books`
It returns list of books based on given parameters.<br/>
You can optionally send the following parameters-<br/>
**i.** category (e.g. Business, Poyetry, Sequential Art)<br/>
**ii.** min_price, max_price<br/>
**iii.** rating<br/>
**iv.** sort_by (e.g. rating, price, reviews)<br/>
**v.** page<br/>
**vi.** page_size<br/>

The endpoint will respond with book data based on given parameters.
If no parameter given it will serve the latest 20 books.


#### **2.** ` GET /books/{book_id}`
It returns details of a single boook based on given **book_id**.<br/>
If no book found for the particular id it returns **404**.


#### **3.** ` GET /changes`
It returns the latest changes detected by the scheduler.<br/>
You can optionally send **page** and **page_size** paramter.
By default it returns latest 20 changes.


You can find the sample documents attached in **Sample_Documents.txt** file.


