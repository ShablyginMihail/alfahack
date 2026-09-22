from __future__ import annotations

import argparse
import hashlib
import secrets


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Управление ключами систем-потребителей")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Сгенерировать новый ключ и его sha256")
    new.add_argument("--name", default="", help="Имя системы для комментария")

    hash_cmd = sub.add_parser("hash", help="Вычислить sha256 ключа")
    hash_cmd.add_argument("key", help="Ключ в открытом виде")

    args = parser.parse_args()

    if args.command == "new":
        key = secrets.token_urlsafe(32)
        digest = sha256_hex(key)
        print(f"key: {key}")
        print(f"sha256: {digest}")
        if args.name:
            print(f"# {args.name}")
    elif args.command == "hash":
        print(sha256_hex(args.key))


if __name__ == "__main__":
    main()
