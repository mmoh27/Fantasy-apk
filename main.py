from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict, dataclass, field
import json

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView


MID_SUBPOSITIONS = {"MID", "DM", "CM", "AMF", "LM", "RM", "LW", "RW"}


def get_base_dir() -> Path:
    app = App.get_running_app()
    candidates: List[Path] = []
    if app is not None and getattr(app, "user_data_dir", None):
        candidates.append(Path(app.user_data_dir) / "fantastiy")
    candidates.append(Path.home() / "fantastiy")
    candidates.append(Path.cwd() / "fantastiy_data")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue

    return Path(".")


def normalize_position(raw_position: str) -> str:
    pos = raw_position.upper().strip()
    if pos in MID_SUBPOSITIONS:
        return "MID"
    if pos in {"GK", "DEF", "FWD"}:
        return pos
    raise ValueError(f"مركز غير معروف: {raw_position}")


@dataclass
class PlayerMatchStats:
    name: str
    position: str
    minutes: int = 0
    yellow_cards: int = 0
    red_card: bool = False
    own_goals: int = 0
    penalties_missed: int = 0
    saves: int = 0
    one_on_one_saves: int = 0
    penalty_saves: int = 0
    clearances_outside_box: int = 0
    goals_conceded: int = 0
    defensive_actions: int = 0
    shots_on_target: int = 0
    chances_created: int = 0
    pre_assists: int = 0
    attacking_contributions: int = 0
    defensive_contributions: int = 0
    woodwork_hits: int = 0
    regular_goals: int = 0
    assists: int = 0
    penalty_goals: int = 0
    header_goals: int = 0
    outside_box_goals: int = 0
    free_kick_goals: int = 0
    bicycle_kick_goals: int = 0
    rabona_goals: int = 0
    is_captain: bool = False
    replaced_by: Optional[str] = None
    breakdown: Dict[str, int] = field(default_factory=dict)

    @property
    def normalized_position(self) -> str:
        return normalize_position(self.position)

    @property
    def total_points(self) -> int:
        return sum(self.breakdown.values())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_appearance_and_clean_sheet(stats: PlayerMatchStats, include_clean_sheet: bool) -> None:
    if stats.minutes >= 70:
        stats.breakdown["المشاركة (70+ دقيقة)"] = 2
    elif stats.minutes > 0:
        stats.breakdown["المشاركة (1-69 دقيقة)"] = 1
    else:
        stats.breakdown["المشاركة (0 دقيقة)"] = 0

    if include_clean_sheet:
        if stats.minutes >= 60 and stats.goals_conceded == 0:
            stats.breakdown["الكلين شيت (60+ دقيقة)"] = 4
        else:
            stats.breakdown["الكلين شيت"] = 0


def calculate_common_penalties(stats: PlayerMatchStats) -> None:
    if stats.yellow_cards > 0:
        stats.breakdown["الإنذارات"] = -1 * stats.yellow_cards
    if stats.red_card:
        stats.breakdown["الطرد"] = -3
    if stats.own_goals > 0:
        stats.breakdown["الأهداف الذاتية"] = -3 * stats.own_goals
    if stats.penalties_missed > 0:
        stats.breakdown["إهدار ركلات الجزاء"] = -3 * stats.penalties_missed


def calculate_gk_points(stats: PlayerMatchStats) -> None:
    calculate_appearance_and_clean_sheet(stats, include_clean_sheet=True)
    if stats.saves >= 2:
        stats.breakdown["التصديات العادية (كل 2)"] = (stats.saves // 2) * 1
    if stats.one_on_one_saves > 0:
        stats.breakdown["التصدي لانفراد"] = stats.one_on_one_saves * 2
    if stats.penalty_saves > 0:
        stats.breakdown["تصدي ركلة جزاء"] = stats.penalty_saves * 4
    if stats.clearances_outside_box > 0:
        stats.breakdown["تشتيت من خارج الـ 18"] = stats.clearances_outside_box * 1
    if stats.assists > 0:
        stats.breakdown["الأسيست"] = stats.assists * 5
    if stats.goals_conceded >= 2:
        stats.breakdown["خصم استقبال الأهداف (كل 2)"] = -(stats.goals_conceded // 2) * 1
    calculate_common_penalties(stats)


def calculate_def_points(stats: PlayerMatchStats) -> None:
    calculate_appearance_and_clean_sheet(stats, include_clean_sheet=True)
    if stats.regular_goals > 0:
        stats.breakdown["الأهداف"] = stats.regular_goals * 6
    if stats.assists > 0:
        stats.breakdown["الأسيست"] = stats.assists * 3
    if stats.goals_conceded >= 2:
        stats.breakdown["خصم استقبال الأهداف (كل 2)"] = -(stats.goals_conceded // 2) * 1
    if stats.defensive_actions >= 4:
        stats.breakdown["التدخلات الدفاعية (كل 4)"] = (stats.defensive_actions // 4) * 1
    if stats.shots_on_target >= 3:
        stats.breakdown["التسديد على المرمى (كل 3)"] = (stats.shots_on_target // 3) * 1
    if stats.chances_created >= 3:
        stats.breakdown["صناعة الفرص (كل 3)"] = (stats.chances_created // 3) * 1
    if stats.pre_assists > 0:
        stats.breakdown["البري أسيست"] = stats.pre_assists * 1
    calculate_common_penalties(stats)


def calculate_mid_points(stats: PlayerMatchStats) -> None:
    calculate_appearance_and_clean_sheet(stats, include_clean_sheet=False)
    if stats.regular_goals > 0:
        stats.breakdown["الأهداف"] = stats.regular_goals * 5
    if stats.assists > 0:
        stats.breakdown["الأسيست"] = stats.assists * 3
    if stats.attacking_contributions >= 4:
        stats.breakdown["المساهمات الهجومية (كل 4)"] = (stats.attacking_contributions // 4) * 1
    if stats.defensive_contributions >= 10:
        stats.breakdown["المساهمات الدفاعية (كل 10)"] = (stats.defensive_contributions // 10) * 2
    if stats.pre_assists >= 2:
        stats.breakdown["البري أسيست (كل 2)"] = (stats.pre_assists // 2) * 1
    if stats.woodwork_hits > 0:
        stats.breakdown["القائم أو العارضة"] = stats.woodwork_hits * 1
    calculate_common_penalties(stats)


def calculate_fwd_points(stats: PlayerMatchStats) -> None:
    calculate_appearance_and_clean_sheet(stats, include_clean_sheet=False)
    if stats.regular_goals > 0:
        stats.breakdown["هدف عادي"] = stats.regular_goals * 4
    if stats.penalty_goals > 0:
        stats.breakdown["هدف من ركلة جزاء"] = stats.penalty_goals * 3
    if stats.header_goals > 0:
        stats.breakdown["هدف بالرأس (هيدنج)"] = stats.header_goals * 4
    if stats.outside_box_goals > 0:
        stats.breakdown["هدف من خارج الـ 18"] = stats.outside_box_goals * 4
    if stats.free_kick_goals > 0:
        stats.breakdown["هدف من ركلة حرة مباشرة"] = stats.free_kick_goals * 5
    if stats.bicycle_kick_goals > 0:
        stats.breakdown["هدف دبل كيك"] = stats.bicycle_kick_goals * 5
    if stats.rabona_goals > 0:
        stats.breakdown["هدف رابونا"] = stats.rabona_goals * 4
    if stats.assists > 0:
        stats.breakdown["الأسيست"] = stats.assists * 3
    if stats.pre_assists > 0:
        stats.breakdown["البري أسيست"] = stats.pre_assists * 1
    if stats.woodwork_hits > 0:
        stats.breakdown["القائم أو العارضة"] = stats.woodwork_hits * 1
    calculate_common_penalties(stats)


def calculate_player_points(stats: PlayerMatchStats) -> PlayerMatchStats:
    pos = stats.normalized_position
    stats.breakdown.clear()
    if pos == "GK":
        calculate_gk_points(stats)
    elif pos == "DEF":
        calculate_def_points(stats)
    elif pos == "MID":
        calculate_mid_points(stats)
    elif pos == "FWD":
        calculate_fwd_points(stats)
    return stats


def apply_captain_bonus(stats: PlayerMatchStats) -> None:
    if stats.is_captain:
        stats.breakdown["بونص الكابتن (×2)"] = stats.total_points


def validate_squad_and_lineup(starting_xi: List[PlayerMatchStats], bench: List[PlayerMatchStats]) -> None:
    if len(starting_xi) != 11:
        raise ValueError(f"التشكيلة الأساسية يجب أن تكون 11 لاعباً، الحالي: {len(starting_xi)}")
    if len(bench) != 4:
        raise ValueError(f"الدكة يجب أن تكون 4 لاعبين، الحالي: {len(bench)}")

    full_squad = starting_xi + bench
    pos_counts = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
    for player in full_squad:
        pos_counts[player.normalized_position] += 1

    if pos_counts != {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}:
        raise ValueError(f"قوام الـ 15 غير مطابق للوائح: {pos_counts}")

    xi_counts = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
    for player in starting_xi:
        xi_counts[player.normalized_position] += 1

    if xi_counts["GK"] != 1:
        raise ValueError("يجب مشاركة حارس مرمى واحد (GK) في التشكيلة الأساسية")
    if xi_counts["DEF"] < 3:
        raise ValueError(f"يجب مشاركة 3 مدافعين (DEF) على الأقل، الحالي: {xi_counts['DEF']}")


def resolve_lineup_with_bench(
    starting_xi: List[PlayerMatchStats],
    bench: List[PlayerMatchStats],
    transfer_penalty_points: int = 0,
) -> Tuple[List[PlayerMatchStats], int]:
    validate_squad_and_lineup(starting_xi, bench)
    used_bench_names = set()
    active_xi: List[PlayerMatchStats] = []

    for starter in starting_xi:
        if starter.minutes == 0:
            replacement = next(
                (
                    b
                    for b in bench
                    if b.name not in used_bench_names
                    and b.normalized_position == starter.normalized_position
                    and b.minutes > 0
                ),
                None,
            )
            if replacement is not None:
                used_bench_names.add(replacement.name)
                if starter.is_captain:
                    replacement.is_captain = True
                    starter.is_captain = False
                calculate_player_points(replacement)
                apply_captain_bonus(replacement)
                active_xi.append(replacement)
                continue

        calculate_player_points(starter)
        apply_captain_bonus(starter)
        active_xi.append(starter)

    total_points = sum(p.total_points for p in active_xi) + transfer_penalty_points
    return active_xi, total_points


@dataclass
class TransferManager:
    current_gameweek: int
    match_kickoff: datetime
    gw_transfers: Dict[int, int] = field(default_factory=dict)
    extra_transfers_used_this_gw: int = 0

    def __post_init__(self) -> None:
        self.gw_transfers = {int(k): int(v) for k, v in self.gw_transfers.items()}
        for gw in (self.current_gameweek, self.current_gameweek + 1):
            self.gw_transfers.setdefault(gw, 1)

    @property
    def deadline(self) -> datetime:
        return self.match_kickoff - timedelta(minutes=30)

    def is_before_deadline(self, now: Optional[datetime] = None) -> bool:
        return (now or datetime.now()) <= self.deadline

    def borrow_next_gameweek_transfer(self, now: Optional[datetime] = None) -> Tuple[bool, str]:
        if not self.is_before_deadline(now):
            return False, "انتهى الديدلاين (قبل الماتش بـ 30 دقيقة)، لا يمكن استلاف تبديلة الآن."
        next_gw = self.current_gameweek + 1
        next_gw_avail = self.gw_transfers.get(next_gw, 1)
        if next_gw_avail <= 0:
            return False, f"لا توجد تبديلة متاحة للاستلاف من الجولة {next_gw}."
        self.gw_transfers[next_gw] = next_gw_avail - 1
        self.gw_transfers[self.current_gameweek] = self.gw_transfers.get(self.current_gameweek, 0) + 1
        return True, (
            f"تم استلاف تبديلة من الجولة {next_gw}. "
            f"رصيد الجولة {self.current_gameweek}: {self.gw_transfers[self.current_gameweek]} | "
            f"رصيد الجولة {next_gw}: {self.gw_transfers[next_gw]}"
        )

    def make_transfer(self, count: int = 1, now: Optional[datetime] = None) -> Tuple[bool, int, str]:
        if count <= 0:
            return False, 0, "عدد التبديلات يجب أن يكون أكبر من صفر."
        if not self.is_before_deadline(now):
            return False, 0, "انتهى الديدلاين (قبل الماتش بـ 30 دقيقة)، التبديلات مقفولة."
        avail = self.gw_transfers.get(self.current_gameweek, 0)
        free_used = min(avail, count)
        paid_used = count - free_used
        self.gw_transfers[self.current_gameweek] = avail - free_used
        self.extra_transfers_used_this_gw += paid_used
        penalty = -3 * paid_used
        msg = (
            f"تم تنفيذ {count} تبديل: ({free_used} مجاني، {paid_used} بخصم {penalty} نقطة). "
            f"المتبقي في الجولة {self.current_gameweek}: {self.gw_transfers[self.current_gameweek]}"
        )
        return True, penalty, msg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_gameweek": self.current_gameweek,
            "match_kickoff": self.match_kickoff.isoformat(),
            "gw_transfers": {str(k): v for k, v in self.gw_transfers.items()},
            "extra_transfers_used_this_gw": self.extra_transfers_used_this_gw,
        }


def build_sample_squad() -> Tuple[List[PlayerMatchStats], List[PlayerMatchStats]]:
    starting_11 = [
        PlayerMatchStats(name="طارق", position="GK", minutes=90, saves=4, goals_conceded=0),
        PlayerMatchStats(name="كريم", position="DEF", minutes=90, goals_conceded=0, regular_goals=1),
        PlayerMatchStats(name="ياسر", position="DEF", minutes=0),
        PlayerMatchStats(name="محمود", position="DEF", minutes=75, goals_conceded=0, defensive_actions=4),
        PlayerMatchStats(name="عمر", position="CM", minutes=85, assists=1, attacking_contributions=4),
        PlayerMatchStats(name="زياد", position="RW", minutes=70, regular_goals=1, is_captain=True),
        PlayerMatchStats(name="هشام", position="DM", minutes=90, defensive_contributions=10),
        PlayerMatchStats(name="باسم", position="AMF", minutes=60, pre_assists=2),
        PlayerMatchStats(name="رامي", position="LM", minutes=45, woodwork_hits=1),
        PlayerMatchStats(name="آدم", position="FWD", minutes=80, regular_goals=1),
        PlayerMatchStats(name="مروان", position="FWD", minutes=65, assists=1),
    ]
    bench_4 = [
        PlayerMatchStats(name="حارس_بديل", position="GK", minutes=0),
        PlayerMatchStats(name="مدافع_بديل_لعب", position="DEF", minutes=90, goals_conceded=0),
        PlayerMatchStats(name="مدافع_بديل_2", position="DEF", minutes=90, assists=1),
        PlayerMatchStats(name="مهاجم_بديل", position="FWD", minutes=20),
    ]
    return starting_11, bench_4


def run_scenario_text(scenario: int) -> str:
    base_dir = get_base_dir()
    save_path = base_dir / "fantasy_demo_save.json"
    report_path = base_dir / "demo_report.txt"

    starting_11, bench_4 = build_sample_squad()
    tm = TransferManager(current_gameweek=10, match_kickoff=datetime.now() + timedelta(hours=2))
    penalty_pts = 0
    lines: List[str] = [f"مسار التخزين: {base_dir}", ""]

    if scenario == 1:
        lines.append("[سيناريو 1] استلاف تبديلة + 3 تبديلات:")
        _, msg_b = tm.borrow_next_gameweek_transfer(now=datetime.now())
        _, penalty_pts, msg_t = tm.make_transfer(count=3, now=datetime.now())
        lines.extend([f"- {msg_b}", f"- {msg_t}"])
    elif scenario == 2:
        tm.match_kickoff = datetime.now() + timedelta(minutes=20)
        ok_b, msg_b = tm.borrow_next_gameweek_transfer(now=datetime.now())
        ok_t, _, msg_t = tm.make_transfer(count=1, now=datetime.now())
        lines.append("[سيناريو 2] اختبار قفل الديدلاين:")
        lines.extend([f"- استلاف ({ok_b}): {msg_b}", f"- تبديل ({ok_t}): {msg_t}"])
    elif scenario == 3:
        lines.append("[سيناريو 3] الدكة التلقائية + الكابتن + تصدير تقرير:")

    active_xi, gw_total = resolve_lineup_with_bench(starting_11, bench_4, penalty_pts)
    lines.append("\n--- التشكيلة الفعالة ---")
    for p in active_xi:
        cap = " [C]" if p.is_captain else ""
        lines.append(f"* {p.name}{cap} ({p.normalized_position}) | دقائق: {p.minutes} | نقاط: {p.total_points}")

    lines.extend([
        "",
        f"مجموع اللاعبين: {sum(p.total_points for p in active_xi)}",
        f"خصم التبديلات: {penalty_pts}",
        f"إجمالي نقاط الجولة: {gw_total}",
    ])

    save_path.write_text(
        json.dumps(
            {
                "saved_at": datetime.now().isoformat(),
                "transfer_manager": tm.to_dict(),
                "total_points": gw_total,
                "active_xi": [p.to_dict() for p in active_xi],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    lines.append(f"\nتم حفظ التقرير في:\n{report_path}")
    return "\n".join(lines)


class FantasyUI(BoxLayout):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", padding=12, spacing=8, **kwargs)

        self.add_widget(Label(text="Fantasy System App", size_hint_y=None, height=44))

        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=6)
        b1 = Button(text="1. Transfers (-3)")
        b2 = Button(text="2. Deadline")
        b3 = Button(text="3. Lineup & Report")
        b1.bind(on_press=lambda _: self.show_scenario(1))
        b2.bind(on_press=lambda _: self.show_scenario(2))
        b3.bind(on_press=lambda _: self.show_scenario(3))
        btn_row.add_widget(b1)
        btn_row.add_widget(b2)
        btn_row.add_widget(b3)
        self.add_widget(btn_row)

        self.output_label = Label(
            text="Press a button above to run a scenario.",
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        self.output_label.bind(texture_size=self._update_height)
        self.output_label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))

        scroll = ScrollView()
        scroll.add_widget(self.output_label)
        self.add_widget(scroll)

    def _update_height(self, instance: Label, size: Tuple[float, float]) -> None:
        instance.height = max(size[1] + 20, 200)

    def show_scenario(self, scenario: int) -> None:
        self.output_label.text = run_scenario_text(scenario)


class FantasyApp(App):
    def build(self) -> FantasyUI:
        return FantasyUI()


if __name__ == "__main__":
    FantasyApp().run()
