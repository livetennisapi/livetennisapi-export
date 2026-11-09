from __future__ import annotations

import csv
import io
import json

import httpx
import pytest

from livetennisapi_export import cli, export, fetch, flatten, write

from conftest import load


def test_matches_follow_has_more_across_pages(make_client):
    client = make_client({"/matches": ["matches_page1.json", "matches_page2.json"]})
    rows = fetch("matches", client=client, page_size=2, status="completed", from_="2026-11-08", to="2026-11-08")

    assert [r["id"] for r in rows] == [5001, 5002, 5003]
    sent = [dict(r.url.params) for r in client.recorder.requests]
    assert [s["offset"] for s in sent] == ["0", "2"]
    assert all(s["status"] == "completed" and s["from"] == "2026-11-08" and s["to"] == "2026-11-08" for s in sent)
    assert all(s["limit"] == "2" for s in sent)


def test_rows_are_the_payload_unchanged(make_client):
    client = make_client({"/fixtures": ["fixtures.json"]})
    assert fetch("fixtures", client=client) == load("fixtures.json")["data"]


def test_max_rows_stops_without_another_request(make_client):
    client = make_client({"/matches": ["matches_page1.json", "matches_page2.json"]})
    rows = fetch("matches", client=client, page_size=2, max_rows=1, status="upcoming")
    assert len(rows) == 1
    assert len(client.recorder.requests) == 1


def test_player_dataset_fetches_each_id(make_client):
    client = make_client(
        {
            "/players/101": ["player_101.json"],
            "/players/202": ["player_202.json"],
        }
    )
    rows = fetch("player", client=client, ids=[101, 202])
    assert [r["id"] for r in rows] == [101, 202]
    paths = [r.url.path for r in client.recorder.requests]
    assert paths == ["/api/public/v1/players/101", "/api/public/v1/players/202"]


def test_rankings_need_one_listable_system(make_client):
    client = make_client({"/rankings": ["rankings_atp.json"]})
    with pytest.raises(ValueError, match="one system"):
        fetch("rankings", client=client)
    with pytest.raises(ValueError, match="utr"):
        fetch("rankings", client=client, system="utr")
    rows = fetch("rankings", client=client, system="atp")
    assert rows[1]["player_id"] is None  # off-roster rows stay in the table
    assert client.recorder.requests[-1].url.params["system"] == "atp"


def test_unknown_dataset_and_parameter_are_refused(make_client):
    client = make_client({})
    with pytest.raises(ValueError, match="unknown dataset"):
        fetch("odds", client=client)
    with pytest.raises(ValueError, match="unknown parameter"):
        fetch("fixtures", client=client, status="live")
    assert client.recorder.requests == []


def test_flatten_dots_objects_and_encodes_lists():
    flat = flatten(load("matches_page1.json")["data"][0])
    assert flat["players.p1.name"] == "Test Player A"
    assert flat["players.p2.data_completeness.known"] == 3
    assert json.loads(flat["score.sets"]) == [2, 0]
    assert json.loads(flat["score.games"]) == [[6, 6], [3, 4]]
    assert "players" not in flat


def test_csv_has_one_header_and_a_row_per_record(tmp_path):
    rows = load("matches_page1.json")["data"] + load("matches_page2.json")["data"]
    out = tmp_path / "m.csv"
    assert write(rows, out) == 3
    parsed = list(csv.DictReader(io.StringIO(out.read_text(encoding="utf-8"))))
    assert len(parsed) == 3
    assert parsed[2]["winner"] == "2"
    assert parsed[0]["indoor"] == "true"
    assert parsed[0]["event_status"] == "Finished"
    assert parsed[0]["players.p1.birthday"] == ""


def test_jsonl_round_trips(tmp_path):
    rows = load("players.json")["data"]
    out = tmp_path / "p.jsonl"
    write(rows, out)
    back = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert back == rows


def test_parquet_reads_back(tmp_path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    rows = load("rankings_atp.json")["data"]
    out = tmp_path / "r.parquet"
    assert write(rows, out) == 2
    frame = pd.read_parquet(out)
    assert list(frame["rank"]) == [12, 13]
    assert frame["player_name"].tolist() == ["Test Player A", "Test Player E"]


def test_format_needs_a_known_extension(tmp_path):
    with pytest.raises(ValueError, match="cannot tell the format"):
        write([], tmp_path / "out.xlsx")


def test_failed_fetch_writes_nothing(make_client, tmp_path):
    client = make_client({"/rankings": lambda r: httpx.Response(403, json=load("upgrade_required.json"))})
    out = tmp_path / "r.csv"
    with pytest.raises(Exception, match="upgrade_required|403"):
        export("rankings", out, client=client, system="atp")
    assert not out.exists()


def test_cli_writes_a_file(make_client, tmp_path, capsys):
    client = make_client({"/tournaments": ["tournaments.json"]})
    out = tmp_path / "t.csv"
    assert cli.main(["tournaments", "--tour", "atp", "-o", str(out)], client=client) == 0
    assert "wrote 1 rows" in capsys.readouterr().err
    assert client.recorder.requests[0].url.params["tour"] == "atp"
    assert out.read_text(encoding="utf-8").splitlines()[0].startswith("id,name,tour")


def test_cli_date_sets_both_bounds(make_client, tmp_path):
    client = make_client({"/matches": ["matches_page2.json"]})
    out = tmp_path / "m.jsonl"
    code = cli.main(["matches", "--status", "completed", "--date", "2026-11-08", "-o", str(out)], client=client)
    assert code == 0
    params = client.recorder.requests[0].url.params
    assert params["from"] == params["to"] == "2026-11-08"


def test_cli_stdout_jsonl(make_client, capsys):
    client = make_client({"/players": ["players.json"]})
    assert cli.main(["players", "test", "-o", "-", "-f", "jsonl"], client=client) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [json.loads(x)["id"] for x in lines] == [101, 303]


def test_cli_reports_an_upgrade_and_exits_1(make_client, tmp_path, capsys):
    client = make_client({"/rankings": lambda r: httpx.Response(403, json=load("upgrade_required.json"))})
    code = cli.main(["rankings", "--system", "atp", "-o", str(tmp_path / "r.csv")], client=client)
    assert code == 1
    err = capsys.readouterr().err
    assert "refused" in err and "PRO" in err


def test_cli_without_a_key_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("LIVETENNISAPI_KEY", raising=False)
    assert cli.main(["fixtures", "-o", str(tmp_path / "f.csv")]) == 2
    assert "LIVETENNISAPI_KEY" in capsys.readouterr().err
