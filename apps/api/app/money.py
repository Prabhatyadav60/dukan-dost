def format_paise(paise: int) -> str:
    """₹1,250 / ₹1,23,450.50 — Indian digit grouping, decimals only when non-zero."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(int(paise)), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return f"{sign}₹{s}" + (f".{p:02d}" if p else "")
