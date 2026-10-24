"""Command-line interface: ``td-arabic <command>``.

The commands are listed (in French, for users) in ``HELP_TEXT`` below, which
is also the ``--help`` description.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HELP_TEXT = """Interface en ligne de commande : td-arabic <commande>.

    extract        PDF du lexique -> data/interim (entrées, texte, pages brutes)
    build-corpus   data/interim -> data/processed (lexique final, corpus)
    pipeline       extract + build-corpus
    stats          statistiques du corpus textuel et audio
    dataset        data/processed + phrases -> data/dataset (entraînement, erreurs)
    translate      traduire un mot ou une phrase
    generate       générer des phrases thématiques (option --save)
    serve          lancer l'API REST
    studio         lancer le studio (génération, traduction, enregistrement)
    finetune       données pour Unsloth + installation d'Unsloth Studio (check, prepare, install, studio)
    validate       lancer l'application de validation de l'extraction
"""

APPS_DIR = Path(__file__).parent / "apps"


def _print_json(data) -> None:
    """Print ``data`` as indented UTF-8 JSON."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_extract(args) -> None:
    """Run step 1: extract the lexicon from the PDF into ``data/interim``.

    Args:
        args: Parsed arguments; ``args.pdf`` optionally overrides the PDF path.
    """
    from td_arabic.lexicon import pdf_extract
    pdf_extract.run(Path(args.pdf) if args.pdf else None)


def cmd_build(args) -> None:
    """Run step 2: build the final lexicon and corpus into ``data/processed``.

    Args:
        args: Parsed arguments (unused).
    """
    from td_arabic.lexicon import corpus
    corpus.run()


def cmd_pipeline(args) -> None:
    """Run the whole pipeline (extract, then build-corpus).

    Args:
        args: Parsed arguments, as for :func:`cmd_extract`.
    """
    cmd_extract(args)
    cmd_build(args)


def cmd_stats(args) -> None:
    """Print text-corpus and audio-corpus statistics as JSON.

    Args:
        args: Parsed arguments (unused).
    """
    from td_arabic.config import PATHS
    from td_arabic.lexicon.corpus import corpus_stats
    from td_arabic.recording.dataset import AudioDataset
    from td_arabic.utils.io import read_csv
    _print_json({"texte": corpus_stats(read_csv(PATHS.corpus_csv)), "audio": AudioDataset().stats()})


def cmd_dataset(args) -> None:
    """Build the training dataset (``data/dataset``) and print its statistics.

    Args:
        args: Parsed arguments (unused).
    """
    from td_arabic.dataset import build
    _print_json(build.run())


def cmd_translate(args) -> None:
    """Translate a word or a sentence.

    A single word, or a phrase that is itself a lexicon entry, prints the JSON
    lookup result; anything else prints a sentence gloss (direction guessed
    when ``auto``).

    Args:
        args: Parsed arguments: ``text`` (list of words), ``direction``,
            ``sentence`` (force sentence mode) and ``verbose`` (print segments).
    """
    from td_arabic.translation.lexicon import get_lexicon
    from td_arabic.translation.sentence import guess_direction, translate_sentence
    text = " ".join(args.text)
    if not args.sentence:
        result = get_lexicon().lookup(text, args.direction)
        if len(text.split()) == 1 or result.status in ("exact_match", "form_match"):
            _print_json(result.as_dict())
            return
    direction = args.direction if args.direction != "auto" else guess_direction(text)
    result = translate_sentence(text, direction)
    print(f"[{direction}] {result.gloss}  (couverture {result.coverage:.0%})")
    if args.verbose:
        _print_json(result.as_dict())


def cmd_generate(args) -> None:
    """Print generated sentences, optionally saving them to the sentence bank.

    Args:
        args: Parsed arguments: ``theme`` (list or None), ``n``, ``seed``,
            ``save``, ``include_settled`` (also generate the already validated or rejected
            sentences) and ``list`` (only list the themes).
    """
    from td_arabic.generation.generator import SentenceGenerator
    generator = SentenceGenerator()
    if args.list:
        _print_json(generator.themes())
        return
    from td_arabic.generation.store import SentenceStore
    settled = set() if args.include_settled else SentenceStore().settled_ids()
    sentences = generator.generate(args.theme, args.n, args.seed, exclude=settled)
    for s in sentences:
        flag = f"  [hors lexique : {', '.join(s.hors_lexique)}]" if s.hors_lexique else ""
        print(f"{s.id}\t{s.td}\t{s.fr}{flag}")
    if args.save:
        added = SentenceStore().add(sentences)
        print(f"\n{added} phrase(s) ajoutée(s) à la banque (statut : brouillon).", file=sys.stderr)


def cmd_finetune(args) -> None:
    """Prepare the training data, or install / launch Unsloth Studio, where the model is trained.

    Args:
        args: Parsed arguments: ``action`` (``check``, ``prepare``, ``install`` or ``studio``),
            ``config`` (another configuration file), ``dry_run`` (``install``: only print the
            command) and ``port`` (``studio``).

    Raises:
        SystemExit: With the exit code of the installer or of Unsloth Studio.
    """
    from td_arabic.config import PATHS
    from td_arabic.finetune import unsloth
    from td_arabic.finetune.data import load_config, prepare
    if args.action == "check":
        _print_json(unsloth.report())
    elif args.action == "prepare":
        stats = prepare(load_config(Path(args.config) if args.config else None))
        _print_json(stats)
        if not stats["train"]:
            print("Aucun exemple d'entraînement : validez des phrases dans le studio, ou activez "
                  "`include_lexicon` (ou `source: dataset`) dans configs/finetune.yaml.", file=sys.stderr)
    elif args.action == "install":
        raise SystemExit(unsloth.install(dry_run=args.dry_run))
    else:
        try:
            raise SystemExit(unsloth.launch(args.port, PATHS.finetune_data))
        except FileNotFoundError as error:
            print(error, file=sys.stderr)
            raise SystemExit(1)


def cmd_serve(args) -> None:
    """Start the REST API with uvicorn.

    Args:
        args: Parsed arguments: ``host``, ``port`` and ``reload``.
    """
    import uvicorn
    uvicorn.run("td_arabic.api.app:app", host=args.host, port=args.port, reload=args.reload)


def _streamlit(app: str, extra: list[str]) -> None:
    """Launch a Streamlit app from ``td_arabic/apps``.

    Args:
        app: File name of the app, e.g. ``"studio.py"``.
        extra: Extra arguments for ``streamlit run`` (given after ``--``).

    Raises:
        SystemExit: Always, with Streamlit's exit code.
    """
    cmd = [sys.executable, "-m", "streamlit", "run", str(APPS_DIR / app), *extra]
    raise SystemExit(subprocess.call(cmd))


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with one sub-command per action.

    Returns:
        The configured parser; each sub-parser sets ``func`` to its handler.
    """
    parser = argparse.ArgumentParser(prog="td-arabic", description=HELP_TEXT,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func, help_ in (("extract", cmd_extract, "extraire le lexique du PDF"),
                              ("pipeline", cmd_pipeline, "extraction + construction du corpus")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--pdf", help="chemin du PDF (défaut : data/raw/…)")
        p.set_defaults(func=func)
    sub.add_parser("build-corpus", help="construire le lexique final et le corpus").set_defaults(func=cmd_build)
    sub.add_parser("stats", help="statistiques du corpus").set_defaults(func=cmd_stats)
    sub.add_parser("dataset", help="construire data/dataset (entrées, phrases, erreurs, exports)").set_defaults(
        func=cmd_dataset)

    p = sub.add_parser("translate", help="traduire un mot ou une phrase")
    p.add_argument("text", nargs="+")
    p.add_argument("-d", "--direction", default="auto", choices=["auto", "ar-fr", "fr-ar"])
    p.add_argument("-s", "--sentence", action="store_true", help="forcer le mode phrase")
    p.add_argument("-v", "--verbose", action="store_true", help="détail des segments")
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("generate", help="générer des phrases thématiques")
    p.add_argument("-t", "--theme", action="append", help="thème (répétable ; tous par défaut)")
    p.add_argument("-n", type=int, default=10, help="phrases par thème")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--save", action="store_true", help="ajouter à data/sentences/phrases.csv")
    p.add_argument("--list", action="store_true", help="lister les thèmes")
    p.add_argument("--include-settled", action="store_true",
                   help="regénérer aussi les phrases déjà validées ou rejetées (exclues par défaut)")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("finetune", help="données d'entraînement et Unsloth Studio (entraînement)")
    p.add_argument("action", choices=["check", "prepare", "install", "studio"],
                   help="check : machine et Unsloth ; prepare : construire data/finetune ; install : installer ou "
                        "mettre à jour Unsloth Studio selon le système ; studio : lancer Unsloth Studio")
    p.add_argument("--config", help="fichier de configuration (défaut : configs/finetune.yaml)")
    p.add_argument("--dry-run", action="store_true", help="install : afficher la commande sans l'exécuter")
    p.add_argument("--port", type=int, default=8888, help="studio : port local (défaut : 8888)")
    p.set_defaults(func=cmd_finetune)

    p = sub.add_parser("serve", help="lancer l'API REST")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    for name, app in (("studio", "studio.py"), ("validate", "validation.py")):
        p = sub.add_parser(name, help=f"lancer l'application {name}")
        p.set_defaults(func=lambda a, app=app: _streamlit(app, a.streamlit_args))
        p.add_argument("streamlit_args", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point of the ``td-arabic`` command.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.
    """
    from td_arabic.utils.env import load_env
    load_env()                       # .env -> environnement (HF_TOKEN pour les téléchargements, API_KEY…)
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
