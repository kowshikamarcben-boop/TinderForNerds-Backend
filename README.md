# ProMatch API (Tinder for Nerds Backend)

ProMatch is a powerful backend API designed to facilitate networking and matching for developers and technology enthusiasts. Built with FastAPI, it provides a robust infrastructure for user profiles, discovery, matching, and real-time messaging.

## 🚀 Key Features

- **User & Profile Management**: Complete onboarding and profile customization.
- **Discovery Engine**: Like and match with other users based on interests and skills.
- **Messaging**: real-time communication between matched users.
- **Availability & Bookings**: Schedule meetings and manage time slots.
- **AI Integration**: Powered by OpenAI for enhanced discovery and moderation.
- **Background Workers**: Asynchronous task processing using ARQ and Redis.
- **Real-time Notifications**: Keep users engaged with timely updates.
- **Admin & Moderation**: Built-in tools for platform management and safety.

## 🛠 Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: [Supabase](https://supabase.com/) (PostgreSQL)
- **Auth**: JWT-based authentication
- **Background Jobs**: [ARQ](https://github.com/samuelcolvin/arq) + [Redis](https://redis.io/)
- **AI Engine**: [OpenAI API](https://openai.com/api/)
- **Monitoring**: [Sentry](https://sentry.io/) & [Structlog](https://www.structlog.org/)
- **Deployment**: [Render](https://render.com/)

## 🏁 Getting Started

### Prerequisites

- Python 3.10+
- Redis (for background workers)
- A Supabase Project
- OpenAI API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd backend
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the root directory based on the variables identified in `render.yaml` or `.env.example` (if present).
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
   SUPABASE_JWT_SECRET=your_jwt_secret
   OPENAI_API_KEY=your_openai_key
   REDIS_URL=redis://localhost:6379
   APP_ENV=development
   ```

### Running Locally

**Start the API Server**:
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`. You can access the interactive documentation at `http://localhost:8000/docs`.

**Start the Background Worker**:
```bash
python -m app.worker
```

## 📂 Project Structure

- `app/main.py`: Entry point and FastAPI application factory.
- `app/routers/`: API route definitions organized by feature.
- `app/models/`: Pydantic models for request/response validation.
- `app/services/`: Business logic layer.
- `app/db/`: Database connection and repository patterns.
- `app/worker/`: Background job handlers.

## 🧪 Testing

Run tests using pytest:
```bash
pytest
```

## 🚢 Deployment

The project is configured for deployment on **Render** via `render.yaml`. It includes definitions for both the web service and the background worker.
