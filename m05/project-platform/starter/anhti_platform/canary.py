import hashlib

PROMPTS = {
    "v1": "You are the support assistant of Giao Hang Anh Ti. Answer in Vietnamese, briefly, and name the policy you used.",
    "v2": "You are the support assistant of Giao Hang Anh Ti. Answer in Vietnamese in at most three sentences. Name the policy "
          "you used and say what the customer should do next.",
}


def bucket(user_id, salt, buckets=100):
    return int(hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:8], 16) % buckets


class CanaryRouter:
    def __init__(self, stable="v1", canary="v2", percent=0, salt="release-2026-11"):
        self.stable, self.canary, self.percent, self.salt = stable, canary, percent, salt

    def route(self, user_id):
        return self.canary if bucket(user_id, self.salt) < self.percent else self.stable

    def prompt_for(self, version):
        return PROMPTS[version]


class RollbackController:
    def __init__(self, router, margin=0.05, min_samples=30, strikes=2, promote_after=6):
        self.router, self.margin, self.min_samples = router, margin, min_samples
        self.strikes_needed, self.promote_after = strikes, promote_after
        self.scores = {router.stable: [], router.canary: []}
        self.state, self.strikes, self.good_checks = "running", 0, 0

    def observe(self, version, score):
        if self.state == "running" and version in self.scores:
            self.scores[version].append(score)

    def check(self):
        # TODO 11: đủ mẫu thì so trung bình hai nhóm: tụt quá margin hai lần liên tiếp thì rollback về 0 phần trăm, đủ promote_after lần tốt thì nâng lên 100 phần trăm
        return "running"
