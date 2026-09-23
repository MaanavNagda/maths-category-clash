import unittest

from game.logic import (GameError, GameState, all_in_wager_cap,
                        finale_wager_cap, rank_percent, rank_points,
                        timer_seconds)


def sample_data(with_bonus=True, with_finale=True):
    def clues():
        return [{"value": v, "question": f"Q{v}", "answer": f"A{v}"}
                for v in (100, 200, 300, 400)]
    rounds = [{"name": "Round 1", "categories": [
        {"name": f"Cat {c}", "clues": clues()} for c in range(4)]}]
    if with_bonus:
        bonus = {"name": "Bonus", "categories": [
            {"name": f"B{c}", "clues": clues()} for c in range(4)]}
        bonus["categories"][0]["clues"][0]["all_in"] = True
        rounds.append(bonus)
    data = {"rounds": rounds}
    if with_finale:
        data["finale"] = {"category": "Finals", "question": "FQ",
                          "answer": "FA", "seconds": 300}
    return data


def ready_state():
    gs = GameState()
    gs.load_data(sample_data())
    gs.set_teams(["A", "B", "C", "D", "E"])
    gs.start_game()   # -> rules
    gs.advance()      # -> board
    return gs


class TestHelpers(unittest.TestCase):
    def test_rank_percent_curve(self):
        self.assertEqual([rank_percent(p) for p in range(5)],
                         [100, 90, 80, 70, 60])

    def test_rank_percent_floor(self):
        self.assertEqual(rank_percent(20), 10)

    def test_rank_points(self):
        self.assertEqual(rank_points(400, 0), 400)
        self.assertEqual(rank_points(400, 1), 360)
        self.assertEqual(rank_points(300, 2), 240)

    def test_timer_seconds(self):
        self.assertEqual(timer_seconds(100), 30)
        self.assertEqual(timer_seconds(200), 60)
        self.assertEqual(timer_seconds(300), 90)
        self.assertEqual(timer_seconds(400), 120)

    def test_all_in_cap(self):
        self.assertEqual(all_in_wager_cap(0), 400)
        self.assertEqual(all_in_wager_cap(250), 400)
        self.assertEqual(all_in_wager_cap(900), 900)

    def test_finale_cap(self):
        self.assertEqual(finale_wager_cap(-50), 0)
        self.assertEqual(finale_wager_cap(0), 0)
        self.assertEqual(finale_wager_cap(500), 500)


class TestFlow(unittest.TestCase):
    def test_setup_guards(self):
        gs = GameState()
        with self.assertRaises(GameError):
            gs.start_game()                    # no data
        gs.load_data(sample_data())
        with self.assertRaises(GameError):
            gs.start_game()                    # no teams
        with self.assertRaises(GameError):
            gs.set_teams(["only one"])
        gs.set_teams(["A", "B"])
        gs.start_game()
        self.assertEqual(gs.phase, "rules")
        gs.advance()
        self.assertEqual(gs.phase, "board")

    def test_question_scoring_order(self):
        gs = ready_state()
        gs.select_tile(0, 0)                   # 100-pt tile
        self.assertEqual(gs.phase, "question")
        for tid in (2, 0, 4):                  # finish order: C, A, E
            gs.toggle_rank(tid)
        gs.reveal_answer()
        self.assertEqual(gs.phase, "answer")
        gs.end_question()
        scores = [t["score"] for t in gs.teams]
        self.assertEqual(scores, [90, 0, 100, 0, 80])
        self.assertEqual(gs.phase, "board")
        with self.assertRaises(GameError):     # tile now used
            gs.select_tile(0, 0)

    def test_toggle_rank_undo(self):
        gs = ready_state()
        gs.select_tile(0, 0)
        gs.toggle_rank(1)
        gs.toggle_rank(2)
        gs.toggle_rank(1)                      # undo team 1
        self.assertEqual(gs.ranking, [2])

    def test_abort_keeps_tile(self):
        gs = ready_state()
        gs.select_tile(1, 2)
        gs.abort_question()
        self.assertEqual(gs.phase, "board")
        gs.select_tile(1, 2)                   # still selectable
        self.assertEqual(gs.phase, "question")

    def test_all_in_flow(self):
        gs = ready_state()
        gs.activate_bonus()                    # round 2 has the All In tile
        gs.select_tile(0, 0)
        self.assertEqual(gs.phase, "wager")
        with self.assertRaises(GameError):
            gs.set_wager(0, 401)               # cap = 400 at score 0
        gs.set_wager(0, 250)
        self.assertEqual(gs.phase, "question")
        with self.assertRaises(GameError):
            gs.toggle_rank(0)                  # ranking disabled for All In
        with self.assertRaises(GameError):
            gs.end_question()                  # must mark result first
        gs.set_all_in_result(True)
        gs.end_question()
        self.assertEqual(gs.teams[0]["score"], 250)

    def test_all_in_wrong_loses_wager(self):
        gs = ready_state()
        gs.activate_bonus()
        gs.select_tile(0, 0)
        gs.set_wager(1, 300)
        gs.set_all_in_result(False)
        gs.end_question()
        self.assertEqual(gs.teams[1]["score"], -300)

    def test_bonus_requires_round2(self):
        gs = GameState()
        gs.load_data(sample_data(with_bonus=False))
        gs.set_teams(["A", "B"])
        gs.start_game()
        gs.advance()
        with self.assertRaises(GameError):
            gs.activate_bonus()

    def test_finale_flow(self):
        gs = ready_state()
        gs.start_finale()
        self.assertEqual(gs.phase, "finale_category")
        gs.advance()
        self.assertEqual(gs.phase, "finale_wagers")
        with self.assertRaises(GameError):
            gs.set_finale_wager(0, 1)          # cap 0 at score 0
        gs.teams[0]["score"] = 500
        gs.set_finale_wager(0, 500)
        gs.start_finale_question()
        self.assertEqual(gs.phase, "finale_question")
        gs.reveal_finale_answer()
        with self.assertRaises(GameError):
            gs.finish_finale()                 # teams unmarked
        for tid in range(5):
            gs.set_finale_result(tid, tid == 0)
        gs.finish_finale()
        self.assertEqual(gs.phase, "standings")
        self.assertEqual(gs.teams[0]["score"], 1000)   # +500 wager
        self.assertEqual(gs.teams[1]["score"], 0)      # wager 0, wrong

    def test_snapshot_hides_answer_from_display(self):
        gs = ready_state()
        gs.select_tile(0, 0)
        disp = gs.snapshot("display")
        self.assertNotIn("answer", disp["active"])
        host = gs.snapshot("host")
        self.assertEqual(host["active"]["answer"], "A100")
        gs.reveal_answer()
        self.assertEqual(gs.snapshot("display")["active"]["answer"], "A100")

    def test_snapshot_hides_finale_until_phase(self):
        gs = ready_state()
        gs.start_finale()
        disp = gs.snapshot("display")
        self.assertNotIn("question", disp["finale"])
        gs.advance()
        gs.start_finale_question()
        self.assertIn("question", gs.snapshot("display")["finale"])
        self.assertNotIn("answer", gs.snapshot("display")["finale"])
        gs.reveal_finale_answer()
        self.assertIn("answer", gs.snapshot("display")["finale"])

    def test_board_complete(self):
        gs = ready_state()
        self.assertFalse(gs.board_complete())
        for c in range(4):
            for i in range(4):
                gs.select_tile(c, i)
                gs.end_question()              # no ranking = 0 pts, tile used
        self.assertTrue(gs.board_complete())


if __name__ == "__main__":
    unittest.main()
