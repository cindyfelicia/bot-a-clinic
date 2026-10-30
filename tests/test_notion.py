from notion import NotionTasks


def make(props):
    n = NotionTasks.__new__(NotionTasks)
    n.props = props
    n.title_prop = "Name"
    n.database_id = "db"
    posted = {}

    class R:
        status_code = 200
        def json(self): return {"url": "https://notion.so/x"}

    class H:
        def post(self, path, json): posted["body"] = json; return R()

    n.http = H()
    return n, posted


def test_only_existing_matching_props_are_sent():
    n, posted = make({
        "Name": {"type": "title"},
        "Due": {"type": "date"},
        "Priority": {"type": "select", "select": {"options": [{"name": "High"}]}},
    })
    url = n.create_task("Fix login", due="2026-11-01", priority="High", status="Done", notes="x")
    props = posted["body"]["properties"]
    assert url == "https://notion.so/x"
    assert props["Due"] == {"date": {"start": "2026-11-01"}}
    assert props["Priority"] == {"select": {"name": "High"}}
    assert "Status" not in props


def test_unknown_priority_option_is_dropped():
    n, posted = make({"Name": {"type": "title"}, "Priority": {"type": "select", "select": {"options": [{"name": "P1"}]}}})
    n.create_task("t", priority="High")
    assert "Priority" not in posted["body"]["properties"]
