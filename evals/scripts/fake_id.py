def fake_id(seed):
    """按校验位合成的假身份证号，不对应真实个人。"""
    body = f"110105199001{seed:05d}"[:17]
    w = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    return body + "10X98765432"[sum(int(body[i]) * w[i] for i in range(17)) % 11]
