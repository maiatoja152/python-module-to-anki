import requests
import bs4
import tempfile
import argparse
import json
import typing


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Anki flashcards for Python modules"
    )
    parser.add_argument("modules", type=str, nargs=argparse.ONE_OR_MORE)
    parser.add_argument("--python-version", type=int, default=3)
    return parser.parse_args()


def get_config() -> dict[str, typing.Any]:
    with open("config.json") as config_file:
        return json.load(config_file)


def get_anki_connect_request(action, **params) -> str:
    request: dict = {
        "action": action,
        "version": 6,
        "params": params,
    }
    return json.dumps(request)


def invoke_anki_connect(
        url: str,
        action: str,
        **params
) -> typing.Any:
    response: requests.Response = requests.post(
        url,
        get_anki_connect_request(action, **params)
    )
    try:
        response.raise_for_status()
    except Exception as e:
        print("Error getting response from AnkiConnect: " + str(e))

    response_table = json.loads(response.text)
    if len(response_table) != 2:
        raise Exception("response has an unexpected number of fields")
    if "error" not in response_table:
        raise Exception("response is missing required error field")
    if "result" not in response_table:
        raise Exception("response is missing required result field")
    if response_table["error"] is not None:
        raise Exception(response_table["error"])
    return response_table["result"]


def add_anki_note(
        anki_connect_url: str,
        anki_deck: str,
        anki_model: str,
        fields: dict[str, str],
        tags: list[str]
) -> int:
    note: dict[str, typing.Any] = {
        "deckName": anki_deck,
        "modelName": anki_model,
        "fields": fields,
        "tags": tags
    }
    return invoke_anki_connect(anki_connect_url, "addNote", note=note)


def add_synopsis_anki_note(
        synopsis: str,
        module: str,
        link: str,
) -> int:
    config = get_config()

    return add_anki_note(
        config["anki-connect-url"],
        config["anki-deck"],
        config["anki-model"],
        {
            "Front": synopsis,
            "Back": module,
            "Hint": config["hint-synopsis"],
            "Back Extra": "",
            "Links": link,
            "Reverse": "",
        },
        config["tags-synopsis"]
    )


def get_synopsis(soup: bs4.BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if not isinstance(h1, bs4.Tag):
        raise Exception("h1 should be an instance of bs4.Tag")
    return "".join(map(str, h1.contents[1:-1]))[3:]


def create_synopsis_note(
        module: str,
        python_version: int
) -> typing.Optional[int]:
    docs_url: str = \
        f"https://docs.python.org/{python_version}/library/{module}.html"
    response: requests.Response = requests.get(docs_url)
    try:
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to get docs for {module}: {str(e)}")
        return None

    with tempfile.TemporaryFile() as html_file:
        for chunk in response.iter_content(100000):
            html_file.write(chunk)

        html_file.seek(0)
        soup: bs4.BeautifulSoup = bs4.BeautifulSoup(html_file, "lxml")
        return add_synopsis_anki_note(
            get_synopsis(soup),
            module,
            docs_url
        )


def gui_browse_notes(note_ids: list[int]) -> list[int]:
    config = get_config()

    return invoke_anki_connect(
        config["anki-connect-url"],
        "guiBrowse",
        query="nid:" + ",".join(map(str, note_ids))
    )


def main() -> int:
    args: argparse.Namespace = get_args()

    note_ids: list[int] = []
    for module in args.modules:
        note_id = create_synopsis_note(module, args.python_version)
        if note_id is None:
            continue
        print(f"Added synopsis note for {module}: {note_id}")
        note_ids.append(note_id)
    gui_browse_notes(note_ids)

    return 0


if __name__ == "__main__":
    main()