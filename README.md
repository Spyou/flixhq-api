# FlixHQ Streaming API

A simple Flask API that scrapes FlixHQ for movie streaming sources and provides VidSrc embed links. Built for developers who need reliable streaming endpoints without the hassle.

## What It Does

- Searches movies/shows on FlixHQ
- Extracts UpCloud, VidCloud, and MegaCloud servers
- Provides VidSrc fallback URLs that always work
- No API key required
- CORS enabled for easy frontend integration

## Quick Start

**Local Setup:**

git clone https://github.com/Spyou/flixhq-api.git
cd flixhq-api
pip install -r requirements.txt
python flixhq_api.py


API runs at `http://localhost:8080`

**Deploy to Railway:**

Just push to GitHub and connect to Railway. It auto-deploys.

## API Endpoints

**Health Check:**
GET /api/health

**Get Trending:**
GET /api/trending?limit=20

**Search:**
GET /api/search?q=spiderman

**Get Streaming Links:**
GET /api/details?url=https://flixhq-tv.lol/movie/watch-avengers-endgame-free-39110

**Example Response:**
{
"success": true,
"data": {
"title": "Avengers: Endgame",
"year": "2019",
"rating": "8.4",
"servers": [
{
"server": "UpCloud",
"url": "https://...",
"type": "iframe"
},
{
"server": "VidSrc.to",
"url": "https://vidsrc.to/embed/movie/299534",
"type": "embed"
}
]
}
}


## Tech Stack

- Flask + Flask-CORS
- Selenium + BeautifulSoup4
- jumpfreedom.com (free TMDB proxy)
- Railway/Render ready

## How It Works

1. Scrapes FlixHQ for movies
2. Clicks server buttons to get iframe URLs
3. Generates VidSrc embed links using TMDB IDs
4. Returns clean JSON with all sources

## Known Issues

- FlixHQ servers may have encryption (use VidSrc fallbacks)
- Railway free tier has limited hours
- Some movies may not have all servers available

## Contributing

Found a bug? Want to improve something?

1. Fork it
2. Create your branch (`git checkout -b feature/cool-stuff`)
3. Commit changes (`git commit -m 'Added cool stuff'`)
4. Push (`git push origin feature/cool-stuff`)
5. Open a Pull Request

## Disclaimer

Educational purposes only. Respect copyright laws. Don't use commercially.

## License

MIT License - use it however you want!

---

**Built for the community** 🎬





