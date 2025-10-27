from .db import init_db
from .handlers import build_application

def main():
    init_db()
    app = build_application()
    app.run_polling()

if __name__ == "__main__":
    main()
