# Finance API

The Flask backend for the finance learning project. This first checkpoint connects
to MariaDB and exposes read-only category endpoints.

## Setup

From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and replace `YOUR_MARIADB_HOST` and `CHANGE_ME` with the MariaDB
machine's LAN IP/hostname and the `finance_owner` password. Keep `.env` private.
If the password contains URL-special characters such as `@`, encode them (for
example, `@` becomes `%40`).

Run the development server:

```sh
flask --app run run --debug
```

Test these endpoints in a browser or with curl:

```sh
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/income-categories
curl http://127.0.0.1:5000/api/spending-categories
```

The backend does not call `create_all()`: your tables remain managed by the
schema SQL for now. Later, Flask-Migrate will replace manual schema changes.
