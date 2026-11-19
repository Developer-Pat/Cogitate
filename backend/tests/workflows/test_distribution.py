"""Distribution layer tests — the pipeline pattern's test suite."""

import json

import pytest

from app.workflows.distribution import (
    DisplayDistributor,
    FileDistributor,
    ToastDistributor,
    WorkflowProduct,
    clear_products,
    create_default_distributors,
    delete_product,
    deliver_product,
)


@pytest.fixture
def product():
    return WorkflowProduct(
        product_type="rss_digest",
        title="RSS Digest — 2026-08-10",
        body="# RSS Digest\n\n- item",
        source_template="rss-monitor",
        created_at="2026-08-10T12:00:00Z",
        meta={"items": 1},
    )


class TestFileDistributor:
    def test_writes_file_and_sets_path(self, product, tmp_path):
        dist = FileDistributor(base_dir=tmp_path)
        result = dist.deliver(product)
        assert result.success is True
        # the UNIQUE timestamped name (the collision fix, 2026-08-18)
        fname = "rss_digest-2026-08-10-120000.md"  # created_at 2026-08-10T12:00:00Z
        assert (tmp_path / fname).exists()
        assert product.path == str(tmp_path / fname)
        content = (tmp_path / fname).read_text(encoding="utf-8")
        assert "RSS Digest" in content
        assert "- item" in content

    def test_same_day_deliveries_get_unique_files(self, tmp_path):
        """The collision regression: same-day same-type products must
        NOT share a file name (2026-08-18)."""
        dist = FileDistributor(base_dir=tmp_path)
        for i, ts in enumerate(["2026-08-10T12:00:00Z", "2026-08-10T13:00:00Z"]):
            dist.deliver(WorkflowProduct(
                product_type="rss_digest", title=f"R{i}", body="b",
                source_template="rss-monitor", created_at=ts,
            ))
        names = sorted(f.name for f in tmp_path.iterdir())
        assert len(names) == 2
        assert names[0] != names[1]

    def test_never_raises_on_error(self, product, tmp_path, monkeypatch):
        dist = FileDistributor(base_dir=tmp_path)

        def boom(*_args, **_kwargs):  # simulate write failure
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.write_text", boom)
        result = dist.deliver(product)
        assert result.success is False
        assert "disk full" in result.detail


class TestDisplayDistributor:
    def test_registers_product_in_index(self, product, tmp_path):
        dist = DisplayDistributor(base_dir=tmp_path)
        result = dist.deliver(product)
        assert result.success is True
        index = json.loads((tmp_path / "products.json").read_text(encoding="utf-8"))
        assert len(index) == 1
        assert index[0]["product_type"] == "rss_digest"
        assert index[0]["title"].startswith("RSS Digest")

    def test_newest_first_and_capped(self, product, tmp_path):
        dist = DisplayDistributor(base_dir=tmp_path)
        dist.MAX_ENTRIES = 3
        for i in range(5):
            p = WorkflowProduct(
                product_type="x",
                title=f"P{i}",
                body="b",
                source_template="t",
                created_at=f"2026-08-10T{i:02d}:00:00Z",
            )
            dist.deliver(p)
        index = json.loads((tmp_path / "products.json").read_text(encoding="utf-8"))
        assert len(index) == 3
        assert index[0]["title"] == "P4"  # newest first


class TestRegistryAndFactory:
    def test_create_default_distributors(self):
        dists = create_default_distributors()
        assert set(dists.keys()) == {"file", "display", "toast", "agent"}
        assert isinstance(dists["file"], FileDistributor)
        assert isinstance(dists["display"], DisplayDistributor)
        assert isinstance(dists["toast"], ToastDistributor)

    def test_deliver_product_uses_named_distributors(self, product, tmp_path):
        dists = {
            "file": FileDistributor(base_dir=tmp_path),
            "display": DisplayDistributor(base_dir=tmp_path),
        }
        results = deliver_product(product, distributors=dists, names=["file"])
        assert len(results) == 1
        assert results[0].success is True
        assert not (tmp_path / "products.json").exists()  # display not used

    def test_deliver_product_defaults_to_all(self, product, tmp_path):
        dists = {
            "file": FileDistributor(base_dir=tmp_path),
            "display": DisplayDistributor(base_dir=tmp_path),
        }
        results = deliver_product(product, distributors=dists)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_unknown_distributor_returns_failed_result(self, product, tmp_path):
        dists = {"file": FileDistributor(base_dir=tmp_path)}
        results = deliver_product(product, distributors=dists, names=["nope"])
        assert results[0].success is False
        assert "unknown distributor" in results[0].detail


class TestDeliverNodesUseDistribution:
    """The monitor deliver nodes must go through the layer (no hardcoded writes)."""

    def test_rss_deliver_registers_product(self, monkeypatch, tmp_path):
        from app.workflows.nodes import monitor_nodes

        # ISOLATE from the live store: the deliver nodes write to
        # data/monitor/ by default — a real write pollutes the dev
        # store (products.json + toasts.json) on every suite run,
        # which the toast poller then drains as phantom activity.
        monkeypatch.setattr(
            "app.workflows.distribution.distributors._products_dir",
            lambda: tmp_path,
        )

        state = {
            "report_text": "## New items\n\n- x",
            "new_items": [{"title": "x", "url": "https://e.com"}],
            "errors": [],
        }
        out = monitor_nodes.rss_deliver_node(state)
        assert out["current_step"] == "rss_deliver"
        # display index exists (delivered via the layer: file+display+toast)
        assert len(out.get("delivery", [])) == 3
        assert all(d["success"] for d in out["delivery"])
        names = {d["distributor"] for d in out["delivery"]}
        assert names == {"file", "display", "toast"}


class TestClearProducts:
    """Stale-data reset — the Products page Clear action."""

    def test_clears_files_and_index_keeps_state(self, product, tmp_path):
        from app.workflows.distribution import clear_products

        # deliver a product (writes file + index)
        FileDistributor(base_dir=tmp_path).deliver(product)
        DisplayDistributor(base_dir=tmp_path).deliver(product)
        # state.json must survive (monitor dedup state, not a product)
        (tmp_path / "state.json").write_text('{"seen": []}', encoding="utf-8")

        removed = clear_products(base_dir=tmp_path)

        assert removed >= 2  # the .md file + products.json
        assert not (tmp_path / "products.json").exists()
        assert not (tmp_path / "rss_digest-2026-08-10.md").exists()
        assert (tmp_path / "state.json").exists()  # kept

    def test_empty_dir_returns_zero(self, tmp_path):
        from app.workflows.distribution import clear_products

        assert clear_products(base_dir=tmp_path) == 0


class TestToastDistributor:
    """The toast channel — app-wide in-app notifications."""

    def test_queues_product(self, product, tmp_path):
        dist = ToastDistributor(base_dir=tmp_path)
        result = dist.deliver(product)
        assert result.success is True
        queue = json.loads((tmp_path / "toasts.json").read_text(encoding="utf-8"))
        assert len(queue) == 1
        assert queue[0]["product_type"] == "rss_digest"
        assert queue[0]["title"].startswith("RSS Digest")

    def test_newest_first_and_capped(self, product, tmp_path):
        dist = ToastDistributor(base_dir=tmp_path)
        dist.MAX_ENTRIES = 3
        for i in range(5):
            p = WorkflowProduct(
                product_type="x",
                title=f"P{i}",
                body="b",
                source_template="t",
                created_at=f"2026-08-10T{i:02d}:00:00Z",
            )
            dist.deliver(p)
        queue = json.loads((tmp_path / "toasts.json").read_text(encoding="utf-8"))
        assert len(queue) == 3
        assert queue[0]["title"] == "P4"  # newest first

    def test_registered_in_factory(self):
        dists = create_default_distributors()
        assert "toast" in dists
        assert isinstance(dists["toast"], ToastDistributor)


class TestDeleteProduct:
    """The single-product delete (Phase G, 2026-08-17)."""

    def _seed(self, tmp_path):
        dist = DisplayDistributor(base_dir=tmp_path)
        dist.deliver(WorkflowProduct(
            product_type="exa_report", title="R1", body="b",
            source_template="exa-panel", created_at="2026-08-17T10:00:00Z",
            path="data/monitor/r1.md",
        ))
        dist.deliver(WorkflowProduct(
            product_type="exa_report", title="R2", body="b",
            source_template="exa-panel", created_at="2026-08-17T11:00:00Z",
            path="data/monitor/r2.md",
        ))

    def test_removes_the_index_entry_only(self, tmp_path):
        self._seed(tmp_path)
        assert delete_product("2026-08-17T10:00:00Z", base_dir=tmp_path) is True
        entries = json.loads((tmp_path / "products.json").read_text(encoding="utf-8"))
        assert [e["title"] for e in entries] == ["R2"]

    def test_unknown_id_returns_false(self, tmp_path):
        self._seed(tmp_path)
        assert delete_product("nope", base_dir=tmp_path) is False
        entries = json.loads((tmp_path / "products.json").read_text(encoding="utf-8"))
        assert len(entries) == 2  # untouched

    def test_removes_the_file_too(self, tmp_path):
        # the entry's path is "data/monitor/r1.md" (relative) — place the
        # file where that resolves against the distributor's base_dir
        self._seed(tmp_path)
        resolved = tmp_path / "data" / "monitor" / "r1.md"
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text("# R1", encoding="utf-8")
        delete_product("2026-08-17T10:00:00Z", base_dir=tmp_path)
        assert not resolved.exists()

    def test_keeps_state_json(self, tmp_path):
        self._seed(tmp_path)
        (tmp_path / "state.json").write_text("{}", encoding="utf-8")
        delete_product("2026-08-17T10:00:00Z", base_dir=tmp_path)
        assert (tmp_path / "state.json").exists()

    def test_deletes_only_the_matching_entry(self, tmp_path):
        """The collision regression: deleting one same-day entry must
        NOT remove its siblings (2026-08-18)."""
        dist = DisplayDistributor(base_dir=tmp_path)
        for i, ts in enumerate(["2026-08-15T09:00:00Z", "2026-08-15T10:00:00Z"]):
            dist.deliver(WorkflowProduct(
                product_type="readiness_report", title=f"R{i}", body="b",
                source_template="readiness-check", created_at=ts,
            ))
        assert delete_product("2026-08-15T09:00:00Z", base_dir=tmp_path) is True
        entries = json.loads((tmp_path / "products.json").read_text(encoding="utf-8"))
        assert [e["title"] for e in entries] == ["R1"]  # only the first went
