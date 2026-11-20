"""Helpers to write curriculum lessons compactly (used once to generate the JSON content files)."""


def L(id, title, level, unit, summary, explanation, fr, examples, exercises):
    ex = []
    for e in exercises:
        if e[1] == "mcq":
            ex.append(dict(id=e[0], type="mcq", prompt=e[2], options=e[3], answer=e[4], explanation=e[5]))
        else:
            ans = e[3] if isinstance(e[3], list) else [e[3]]
            ex.append(dict(id=e[0], type=e[1], prompt=e[2], answer=ans, explanation=e[4]))
    return dict(id=id, title=title, level=level, unit=unit, summary=summary, explanation=explanation,
                explanation_fr=fr, examples=[dict(en=a, note=b) for a, b in examples], exercises=ex)
