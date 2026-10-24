"""Tests of the training data written for Unsloth Studio and of its installation per system."""

import json

import pandas as pd

from td_arabic.finetune import unsloth
from td_arabic.finetune.data import build_dataset, in_validation, load_config, pair_examples, write_dataset

SETTINGS = {"include_lexicon": True, "include_validated_sentences": True, "include_expressions": True,
            "directions": ["fr-ar", "ar-fr"], "valid_ratio": 0.2, "system_prompt": "Traduis."}


def _write(tmp_path):
    corpus = tmp_path / "corpus.csv"
    pd.DataFrame([{"src": f"mot{i}", "pos": "n.m.", "output": f"sens{i}", "forms": "", "sense_number": ""}
                  for i in range(100)] + [{"src": "ila l-abad", "pos": "n.m.", "output": "pour toujours",
                                           "forms": "expr.", "sense_number": "2"}]).to_csv(corpus, index=False)
    bank = tmp_path / "phrases.csv"
    pd.DataFrame([{"id": "mar-1", "td": "Ana nachri sukkar.", "fr": "J'achète du sucre.", "statut": "validee"},
                  {"id": "mar-2", "td": "Brouillon.", "fr": "Brouillon.", "statut": "brouillon"}]).to_csv(bank, index=False)
    return corpus, bank


def test_examples_are_chats_in_both_directions():
    ex = pair_examples("lex:abad", "adorer Dieu", "abad", "lexique", ["fr-ar", "ar-fr"], "Traduis.")
    assert [e["direction"] for e in ex] == ["fr-ar", "ar-fr"]
    assert ex[0]["messages"][1]["content"] == "Traduis en arabe tchadien : adorer Dieu"
    assert ex[0]["messages"][2] == {"role": "assistant", "content": "abad"}
    assert ex[1]["messages"][1]["content"] == "Traduis en français : abad" and ex[1]["messages"][2]["content"] == "adorer Dieu"


def test_only_validated_sentences_and_no_pair_leaks_into_validation(tmp_path):
    corpus, bank = _write(tmp_path)
    train, valid = build_dataset(SETTINGS, corpus, bank)
    texts = json.dumps(train + valid, ensure_ascii=False)
    assert "J'achète du sucre." in texts and "Brouillon." not in texts          # jamais les brouillons
    assert {e["pair_id"] for e in train}.isdisjoint({e["pair_id"] for e in valid})  # une paire = un seul côté
    assert 0 < len(valid) < len(train) and len(train + valid) == 2 * 102      # 100 mots + 1 expression + 1 phrase
    no_expr, _ = build_dataset({**SETTINGS, "include_expressions": False, "valid_ratio": 0}, corpus, bank)
    assert "ila l-abad" not in json.dumps(no_expr)


def test_validation_split_is_stable():
    assert in_validation("lex:abad", 0.3) == in_validation("lex:abad", 0.3)
    share = sum(in_validation(f"lex:{i}", 0.1) for i in range(5000)) / 5000
    assert 0.08 < share < 0.12


def test_write_dataset(tmp_path):
    corpus, bank = _write(tmp_path)
    stats = write_dataset(*build_dataset(SETTINGS, corpus, bank), tmp_path / "ft")
    assert stats["train"] + stats["valid"] == 204 and stats["par_source"] == {"lexique": 202, "phrase": 2}
    first = json.loads((tmp_path / "ft" / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(first) == {"messages"}                                   # ChatML : reconnu tel quel par Unsloth
    assert [m["role"] for m in first["messages"]] == ["system", "user", "assistant"]


def test_shipped_config_is_complete():
    config = load_config()
    assert isinstance(config["seed"], int) and "brouillon" not in config["data"]["system_prompt"]
    assert not {"backend", "model", "lora", "training"} & set(config)       # réglages faits dans Unsloth Studio


def test_training_examples_are_shuffled_but_reproducible(tmp_path):
    examples = [pair_examples(f"p{i}", f"fr{i}", f"td{i}", "lexique", ["fr-ar"], "S.")[0] for i in range(50)]
    write_dataset(examples, [], tmp_path / "a")
    write_dataset(examples, [], tmp_path / "b")
    a = (tmp_path / "a" / "train.jsonl").read_text(encoding="utf-8")
    assert a == (tmp_path / "b" / "train.jsonl").read_text(encoding="utf-8")            # même graine, même ordre
    questions = [json.loads(line)["messages"][1]["content"] for line in a.splitlines()]
    assert questions[:5] != [f"Traduis en arabe tchadien : fr{i}" for i in range(5)]


def test_choose_n_pairs_reproducible_nested_and_evaluation_unchanged(tmp_path):
    corpus, bank = _write(tmp_path)
    full_train, full_valid = build_dataset(SETTINGS, corpus, bank)
    small_train, small_valid = build_dataset({**SETTINGS, "max_pairs": 10}, corpus, bank)
    big_train, _ = build_dataset({**SETTINGS, "max_pairs": 40}, corpus, bank)
    pairs = lambda ex: {e["pair_id"] for e in ex}                                       # noqa: E731
    assert len(pairs(small_train)) == 10 and len(small_train) == 20                     # 10 paires × 2 sens
    assert pairs(small_train) <= pairs(big_train) <= pairs(full_train)                   # sous-ensembles emboîtés
    assert pairs(small_train) == pairs(build_dataset({**SETTINGS, "max_pairs": 10}, corpus, bank)[0])
    assert small_valid == full_valid                                                     # évaluation identique
    assert build_dataset({**SETTINGS, "max_pairs": 0}, corpus, bank)[0] == full_train


def test_default_data_is_validated_sentences_only():
    data = load_config()["data"]
    assert data["include_validated_sentences"] is True
    assert data["include_lexicon"] is False and data["include_expressions"] is False and data["max_pairs"] == 0


def _multitask_examples():
    def ex(uid, task, split, question, answer, sources, **meta):
        return {"id": uid, "task": task, "split": split, "source_ids": sources, **meta,
                "messages": [{"role": "system", "content": "Consigne du jeu de données."},
                             {"role": "user", "content": question}, {"role": "assistant", "content": answer}]}
    return [ex("a:ar-fr", "traduction_mot", "train", "Traduis en français : abyad", "blanc", ["td:abyad"],
               direction="ar-fr"),
            ex("g:fr-ar", "traduction_mot", "probe", "Comment dit-on « blanc » ?", "abyad", ["td:abyad"],
               direction="fr-ar"),
            ex("a:flex", "flexion", "dev", "Donne le pluriel de « abyad ».", "buyud", ["td:abyad"]),
            ex("a:orth", "orthographe", "test", "Corrige l'orthographe : djambah", "jambah", ["td:jambah"]),
            ex("p1:fr-ar", "traduction_phrase", "train", "Traduis en arabe tchadien : C'est blanc.", "Hu abyad.",
               ["phr:1"], direction="fr-ar"),
            ex("p1:ar-fr", "traduction_phrase", "train", "Traduis en français : Hu abyad.", "C'est blanc.",
               ["phr:1"], direction="ar-fr")]


def test_dataset_source_keeps_its_split_tasks_and_inference_prompt(tmp_path, monkeypatch):
    from td_arabic.finetune import data as ft_data
    monkeypatch.setattr(ft_data, "load_dataset_exports", lambda folder=None: _multitask_examples())
    settings = {**SETTINGS, "source": "dataset", "system_prompt": "Consigne de l'inférence."}
    train, valid = build_dataset(settings)
    assert {e["id"] for e in train} == {"a:ar-fr", "p1:fr-ar", "p1:ar-fr"}
    assert {e["id"] for e in valid} == {"g:fr-ar", "a:flex"}                     # dev + probe ; jamais test
    assert all(e["messages"][0]["content"] == "Consigne de l'inférence." for e in train + valid)
    assert {e["source"] for e in train} == {"lexique", "phrase"}
    train, valid = build_dataset({**settings, "tasks": ["traduction_phrase"], "directions": ["fr-ar"]})
    assert [e["id"] for e in train] == ["p1:fr-ar"] and valid == []
    train, _ = build_dataset({**settings, "max_pairs": 1})
    assert len({e["pair_id"] for e in train}) == 1                               # les deux sens d'une phrase ensemble
    stats = write_dataset(*build_dataset(settings), folder=tmp_path)
    assert stats["par_tache"] == {"traduction_mot": 2, "traduction_phrase": 2, "flexion": 1}


def test_dataset_exports_are_read_from_disk(tmp_path):
    from td_arabic.finetune.data import load_dataset_exports
    for split in ("train", "dev", "probe"):
        rows = [e for e in _multitask_examples() if e["split"] == split]
        (tmp_path / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert {e["split"] for e in load_dataset_exports(tmp_path)} == {"train", "dev", "probe"}



def test_installer_is_the_official_one_of_each_system():
    assert unsloth.install_command("mac") == ["sh", "-c", "curl -fsSL https://unsloth.ai/install.sh | sh"]
    assert unsloth.install_command("linux") == unsloth.install_command("mac")
    windows = unsloth.install_command("windows")
    assert windows[0] == "powershell" and windows[-1] == "irm https://unsloth.ai/install.ps1 | iex"


def test_system_name(monkeypatch):
    for platform, name in (("darwin", "mac"), ("win32", "windows"), ("linux", "linux")):
        monkeypatch.setattr(unsloth.sys, "platform", platform)
        assert unsloth.system_name() == name


def test_warnings_say_what_prevents_training():
    everything = lambda tool: f"/usr/bin/{tool}"                                        # noqa: E731
    nothing = lambda tool: None                                                         # noqa: E731
    assert unsloth.warnings_for("mac", "arm64", False, everything) == []               # Mac M : MLX, rien ne manque
    assert "brew install git cmake" in unsloth.warnings_for("mac", "arm64", False, nothing)[0]
    assert "Mac Intel" in unsloth.warnings_for("mac", "x86_64", False, everything)[0]
    assert unsloth.warnings_for("linux", "x86_64", True, everything) == []
    assert "GPU NVIDIA" in unsloth.warnings_for("linux", "x86_64", False, everything)[0]
    assert any("Build Tools" in w for w in unsloth.warnings_for("windows", "AMD64", True, everything))


def test_install_runs_the_installer_once_and_dry_run_runs_nothing(monkeypatch):
    monkeypatch.setattr(unsloth.sys, "platform", "darwin")
    calls = []
    assert unsloth.install(dry_run=True, runner=calls.append) == 0 and calls == []
    assert unsloth.install(runner=lambda cmd: calls.append(cmd) or 0) == 0
    assert calls == [unsloth.install_command("mac")]


def test_studio_is_found_in_its_own_folder_and_launched(tmp_path, monkeypatch):
    monkeypatch.setattr(unsloth.sys, "platform", "linux")
    monkeypatch.setattr(unsloth.shutil, "which", lambda name: None)
    monkeypatch.setenv("UNSLOTH_STUDIO_HOME", str(tmp_path))
    assert unsloth.unsloth_command() is None
    exe = tmp_path / "unsloth_studio" / "bin" / "unsloth"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert unsloth.unsloth_command() == str(exe)
    calls = []
    assert unsloth.launch(9000, tmp_path, runner=lambda cmd: calls.append(cmd) or 0) == 0
    assert calls == [[str(exe), "studio", "-p", "9000"]]


def test_launch_without_installation_explains_what_to_do(monkeypatch, tmp_path):
    monkeypatch.setattr(unsloth, "unsloth_command", lambda: None)
    try:
        unsloth.launch()
    except FileNotFoundError as error:
        assert "finetune install" in str(error)
    else:
        raise AssertionError("launch aurait dû échouer")
