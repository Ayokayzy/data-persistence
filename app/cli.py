import json
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import current_app

from app import db
from app.models import Profile


def _parse_timestamp(value):
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    raise ValueError('Invalid timestamp value in seed data')


def register_cli_commands(app):
    @app.cli.command('seed-profiles')
    @click.argument('json_file', type=click.Path(exists=True, path_type=Path))
    @click.option(
        '--progress-every',
        default=100,
        show_default=True,
        type=int,
        help='Show a progress update after every N processed rows.',
    )
    def seed_profiles(json_file, progress_every):
        """Seed profiles from a JSON file."""
        with json_file.open('r', encoding='utf-8') as fh:
            payload = json.load(fh)

        if isinstance(payload, dict) and 'profiles' in payload:
            payload = payload['profiles']
        if not isinstance(payload, list):
            raise click.ClickException('Seed JSON must be an array of profile objects.')
        if progress_every <= 0:
            progress_every = 100

        total = len(payload)
        inserted = 0
        skipped = 0
        processed = 0
        started_at = time.monotonic()
        click.echo(f'Starting seed. total={total} source={json_file}')

        try:
            for item in payload:
                processed += 1
                if not isinstance(item, dict):
                    raise click.ClickException('Each JSON array item must be an object.')

                name = str(item.get('name', '')).strip()
                if not name:
                    skipped += 1
                    continue

                existing = Profile.query.filter(db.func.lower(Profile.name) == name.lower()).first()
                if existing:
                    skipped += 1
                    continue

                profile = Profile(
                    name=name,
                    gender=item.get('gender'),
                    gender_probability=item.get('gender_probability'),
                    sample_size=item.get('sample_size'),
                    age=item.get('age'),
                    age_group=item.get('age_group'),
                    country_id=item.get('country_id'),
                    country_name=item.get('country_name'),
                    country_probability=item.get('country_probability'),
                    created_at=_parse_timestamp(item.get('created_at')),
                    updated_at=_parse_timestamp(item.get('updated_at')),
                )
                db.session.add(profile)
                inserted += 1

                if processed % progress_every == 0 or processed == total:
                    elapsed = time.monotonic() - started_at
                    click.echo(
                        f'Progress: processed={processed}/{total} '
                        f'inserted={inserted} skipped={skipped} elapsed_s={elapsed:.2f}'
                    )

            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            raise click.ClickException(f'Failed to seed profiles: {exc}') from exc

        elapsed = time.monotonic() - started_at
        click.echo(
            f'Seed complete. processed={processed} inserted={inserted} skipped={skipped} '
            f'elapsed_s={elapsed:.2f} source={json_file} app={current_app.name}'
        )
