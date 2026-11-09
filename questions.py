# Banco de preguntas: (nivel, enunciado, opciones, índice correcto)
LEVELS = ["A1", "A2", "B1", "B2", "C1"]
PASS_RATIO = 0.75  # % mínimo para "aprobar" un nivel

RAW = [
 ("A1", "She ___ a teacher.", ["am", "is", "are", "be"], 1),
 ("A1", "What ___ your name?", ["is", "are", "do", "does"], 0),
 ("A1", "I ___ two brothers.", ["has", "have", "am", "is"], 1),
 ("A1", "___ you like pizza?", ["Is", "Are", "Do", "Does"], 2),
 ("A2", "Yesterday we ___ to the cinema.", ["go", "goes", "went", "going"], 2),
 ("A2", "There isn't ___ milk in the fridge.", ["some", "any", "a", "many"], 1),
 ("A2", "My sister is ___ than me.", ["tall", "taller", "the tallest", "more tall"], 1),
 ("A2", "I'm ___ to visit my grandparents this weekend.", ["go", "going", "goes", "went"], 1),
 ("B1", "If it rains tomorrow, we ___ at home.", ["stay", "stayed", "will stay", "would stay"], 2),
 ("B1", "I have lived in Cali ___ 2015.", ["for", "since", "from", "during"], 1),
 ("B1", "She asked me where ___.", ["do I live", "I lived", "did I live", "I live is"], 1),
 ("B1", "The book ___ by millions of people.", ["has read", "was read", "is reading", "read"], 1),
 ("B2", "If I ___ more time, I would learn another language.", ["have", "had", "would have", "will have"], 1),
 ("B2", "He suggested ___ a taxi to the airport.", ["to take", "taking", "take", "took"], 1),
 ("B2", "By next year, she ___ her degree.", ["will finish", "finishes", "will have finished", "has finished"], 2),
 ("B2", "I wish I ___ the answer yesterday.", ["knew", "know", "had known", "have known"], 2),
 ("C1", "Not only ___ late, but he also forgot the documents.", ["he arrived", "did he arrive", "he did arrive", "arrived he"], 1),
 ("C1", "The manager insisted that every employee ___ the training.", ["attends", "attend", "attended", "will attend"], 1),
 ("C1", "Had I known about the delay, I ___ earlier.", ["would leave", "will have left", "would have left", "had left"], 2),
 ("C1", "She is said ___ the best chef in the city.", ["being", "to be", "to being", "be"], 1),
]

QUESTIONS = [
    {"id": i, "level": lv, "text": t, "options": o, "answer": a}
    for i, (lv, t, o, a) in enumerate(RAW)
]

def grade(answers):
    """answers: {question_id: option_index}. Devuelve (nivel, puntaje, total, detalle)."""
    per = {lv: [0, 0] for lv in LEVELS}
    for q in QUESTIONS:
        per[q["level"]][1] += 1
        if answers.get(q["id"]) == q["answer"]:
            per[q["level"]][0] += 1
    level = "Pre-A1"
    for lv in LEVELS:  # el nivel es el último aprobado sin saltos
        ok, n = per[lv]
        if n and ok / n >= PASS_RATIO:
            level = lv
        else:
            break
    score = sum(v[0] for v in per.values())
    return level, score, len(QUESTIONS), per
