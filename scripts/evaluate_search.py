import json
from datetime import UTC, datetime
from pathlib import Path

from psycopg.rows import dict_row

from app.core import db
from app.core.config import settings
from app.llm import embeddings
from app.repositories import search as search_repo

POSITIVE = [
    (
        "Какая минимальная сумма частичного досрочного погашения?",
        "early_repayment_rules.docx",
        "Минимальная сумма частичного досрочного погашения",
    ),
    (
        "Нужно ли платить комиссию за досрочное погашение?",
        "early_repayment_rules.docx",
        "без комиссий и штрафов",
    ),
    (
        "За сколько дней нужно предупредить банк о досрочном погашении?",
        "early_repayment_rules.docx",
        "не позднее чем за 1 рабочий день",
    ),
    (
        "Когда будет доступен новый график после досрочного погашения?",
        "early_repayment_rules.docx",
        "на следующий рабочий день",
    ),
    (
        "Какие числа можно выбрать для ежемесячного платежа?",
        "payment_date_reglament.pdf",
        "только с 1 по 28",
    ),
    (
        "Как часто разрешено менять дату платежа?",
        "payment_date_reglament.pdf",
        "не чаще одного раза в 12 месяцев",
    ),
    (
        "Сколько времени сотрудник рассматривает заявление о смене даты платежа?",
        "payment_date_reglament.pdf",
        "в течение 2 рабочих дней",
    ),
    (
        "Как начисляются проценты между старой и новой датой платежа?",
        "payment_date_reglament.pdf",
        "исходя из 365 дней в году",
    ),
    (
        "Какая ставка по семейной ипотеке?",
        "tariffs.xlsx",
        "IP-FAMILY-6",
    ),
    (
        "Какая ставка по ипотеке для IT-специалистов?",
        "tariffs.xlsx",
        "IP-IT-5",
    ),
    (
        "Сколько стоит дубликат кредитного договора?",
        "tariffs.xlsx",
        "Дубликат кредитного договора",
    ),
    (
        "Какая неустойка предусмотрена за просрочку платежа?",
        "credit_agreement.pdf",
        "0,06%",
    ),
]

NEGATIVE = [
    "как приготовить борщ",
    "Какая погода завтра в Москве?",
    "Как установить драйвер видеокарты?",
    "Кто выиграл чемпионат мира по футболу?",
    "Как ухаживать за комнатной орхидеей?",
]


def main():
    model = settings.embedding_model
    with db.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.id, c.text, d.filename
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.status = 'indexed'
              AND c.embedding IS NOT NULL
              AND c.embedding_model = %s
            """,
            (model,),
        )
        catalog = cur.fetchall()

    cases = []
    for query, filename, needle in POSITIVE:
        matches = [
            row
            for row in catalog
            if row["filename"] == filename
            and needle.casefold() in row["text"].casefold()
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Ожидался один чанк: {filename}, {needle!r}; найдено {len(matches)}"
            )
        cases.append((query, matches[0]["id"]))
    cases.extend((query, None) for query in NEGATIVE)

    samples = []
    for query, expected_id in cases:
        vector = embeddings.embed_query(query)
        with db.connection() as conn:
            rows = search_repo.search(
                conn,
                query=query,
                mode="vector",
                vector=vector,
                model=model,
                threshold=-1.0,
                codes=[],
                limit=len(catalog),
            )

        sample = {
            "query": query,
            "kind": "positive" if expected_id is not None else "negative",
            "expected_id": expected_id,
            "top": rows[:3],
        }
        print(f"\n[{sample['kind']}] {query}")
        print(f"Первый результат: {rows[0]['similarity']:.6f}, {rows[0]['filename']}")

        if expected_id is not None:
            position = next(i for i, row in enumerate(rows, 1) if row["id"] == expected_id)
            target = rows[position - 1]
            sample["expected_rank"] = position
            sample["expected_similarity"] = target["similarity"]
            sample["expected_chunk"] = target
            print(f"Нужный чанк: {target['similarity']:.6f}, место {position}")
        samples.append(sample)

    minimum = min(s["expected_similarity"] for s in samples if s["kind"] == "positive")
    maximum = max(s["top"][0]["similarity"] for s in samples if s["kind"] == "negative")
    report = {
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "vector",
        "threshold_used": -1.0,
        "min_expected_similarity": minimum,
        "max_negative_similarity": maximum,
        "samples": samples,
    }
    path = Path("/tmp/bank-search-calibration.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nМинимум среди нужных чанков: {minimum:.6f}")
    print(f"Максимум среди вопросов не по теме: {maximum:.6f}")
    print(f"Отчёт: {path}")


if __name__ == "__main__":
    main()

