from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, redirect, render_template_string, request, url_for


MID_SUBPOSITIONS = {"MID", "DM", "CM", "AMF", "LM", "RM", "LW", "RW"}


def get_base_dir() -> Path:
    candidates = [
        Path.home() / "fantastiy",
        Path.cwd() / "fantastiy_data",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue
    return Path(".")


BASE_DIR = get_base_dir()
SAVE_PATH = BASE_DIR / "fantasy_web_save.json"
REPORT_PATH = BASE_DIR / "web_report.txt"


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
        starter.replaced_by = None
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
                starter.replaced_by = replacement.name
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
    current_gameweek: int = 10
    match_kickoff: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=2))
    gw_transfers: Dict[int, int] = field(default_factory=dict)
    extra_transfers_used_this_gw: int = 0
    penalty_points: int = 0
    last_message: str = "جاهز للتبديلات."

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
            self.last_message = "انتهى الديدلاين (قبل الماتش بـ 30 دقيقة)، لا يمكن استلاف تبديلة الآن."
            return False, self.last_message
        next_gw = self.current_gameweek + 1
        next_gw_avail = self.gw_transfers.get(next_gw, 1)
        if next_gw_avail <= 0:
            self.last_message = f"لا توجد تبديلة متاحة للاستلاف من الجولة {next_gw}."
            return False, self.last_message
        self.gw_transfers[next_gw] = next_gw_avail - 1
        self.gw_transfers[self.current_gameweek] = self.gw_transfers.get(self.current_gameweek, 0) + 1
        self.last_message = (
            f"تم استلاف تبديلة من الجولة {next_gw}. "
            f"رصيد الجولة {self.current_gameweek}: {self.gw_transfers[self.current_gameweek]} | "
            f"رصيد الجولة {next_gw}: {self.gw_transfers[next_gw]}"
        )
        return True, self.last_message

    def make_transfer(self, count: int = 1, now: Optional[datetime] = None) -> Tuple[bool, int, str]:
        if count <= 0:
            self.last_message = "عدد التبديلات يجب أن يكون أكبر من صفر."
            return False, 0, self.last_message
        if not self.is_before_deadline(now):
            self.last_message = "انتهى الديدلاين (قبل الماتش بـ 30 دقيقة)، التبديلات مقفولة."
            return False, 0, self.last_message
        avail = self.gw_transfers.get(self.current_gameweek, 0)
        free_used = min(avail, count)
        paid_used = count - free_used
        self.gw_transfers[self.current_gameweek] = avail - free_used
        self.extra_transfers_used_this_gw += paid_used
        penalty = -3 * paid_used
        self.penalty_points += penalty
        self.last_message = (
            f"تم تنفيذ {count} تبديل: ({free_used} مجاني، {paid_used} بخصم {penalty} نقطة). "
            f"المتبقي في الجولة {self.current_gameweek}: {self.gw_transfers[self.current_gameweek]}"
        )
        return True, penalty, self.last_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_gameweek": self.current_gameweek,
            "match_kickoff": self.match_kickoff.isoformat(),
            "gw_transfers": {str(k): v for k, v in self.gw_transfers.items()},
            "extra_transfers_used_this_gw": self.extra_transfers_used_this_gw,
            "penalty_points": self.penalty_points,
            "last_message": self.last_message,
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


STARTING_XI, BENCH_4 = build_sample_squad()
TRANSFER_MGR = TransferManager(current_gameweek=10, match_kickoff=datetime.now() + timedelta(hours=2))
STATUS_BANNER = "مرحب بك في صفحة لعبة الفانتازي التفاعلية! عدّل أرقام اللاعبين أو جرّب التبديلات والديدلاين."


def save_report_and_json(active_xi: List[PlayerMatchStats], gw_total: int, extra_notes: str = "") -> str:
    lines: List[str] = [f"مسار التخزين: {BASE_DIR}"]
    if extra_notes:
        lines.append(extra_notes)
    lines.append("\n--- التشكيلة الفعالة ---")
    for p in active_xi:
        cap = " [C]" if p.is_captain else ""
        lines.append(f"* {p.name}{cap} ({p.normalized_position}) | دقائق: {p.minutes} | نقاط: {p.total_points}")
    lines.extend([
        "",
        f"مجموع اللاعبين: {sum(p.total_points for p in active_xi)}",
        f"خصم التبديلات: {TRANSFER_MGR.penalty_points}",
        f"إجمالي نقاط الجولة: {gw_total}",
    ])

    SAVE_PATH.write_text(
        json.dumps(
            {
                "saved_at": datetime.now().isoformat(),
                "transfer_manager": TRANSFER_MGR.to_dict(),
                "total_points": gw_total,
                "active_xi": [p.to_dict() for p in active_xi],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return str(REPORT_PATH)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Fantasy System Web</title>
  <style>
    body { font-family: Tahoma, Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 16px; color: #1f2937; }
    .container { max-width: 1100px; margin: auto; }
    .card { background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); }
    .banner { background: #eef6ff; border-right: 4px solid #2563eb; padding: 12px 14px; border-radius: 8px; margin-bottom: 16px; }
    .error { background: #fef2f2; border-right: 4px solid #dc2626; color: #991b1b; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
    .stat-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; }
    .stat-box strong { display: block; font-size: 20px; color: #111827; margin-top: 4px; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    button, .btn { background: #2563eb; color: #fff; border: none; padding: 9px 14px; border-radius: 7px; cursor: pointer; font-size: 14px; }
    button:hover { background: #1d4ed8; }
    button.secondary { background: #4b5563; }
    button.secondary:hover { background: #374151; }
    button.warn { background: #d97706; }
    button.warn:hover { background: #b45309; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
    th, td { border: 1px solid #e5e7eb; padding: 7px; text-align: center; }
    th { background: #f3f4f6; }
    input[type="number"] { width: 58px; padding: 4px; text-align: center; border: 1px solid #cbd5e1; border-radius: 5px; }
    .cap-badge { background: #16a34a; color: #fff; padding: 2px 6px; border-radius: 5px; font-size: 11px; }
    .sub-note { font-size: 11px; color: #6b7280; display: block; }
  </style>
</head>
<body>
  <div class="container">
    <h2>نظام الفانتازي التفاعلي (نسخة الويب)</h2>

    <div class="banner {% if error_msg %}error{% endif %}">
      {{ error_msg or status_banner }}
    </div>

    <div class="card">
      <h3>ملخص الجولة والتبديلات</h3>
      <div class="stats-grid">
        <div class="stat-box"><span>إجمالي نقاط الجولة</span><strong>{{ gw_total }}</strong></div>
        <div class="stat-box"><span>مجموع نقاط اللاعبين</span><strong>{{ players_total }}</strong></div>
        <div class="stat-box"><span>خصم التبديلات</span><strong>{{ tm.penalty_points }}</strong></div>
        <div class="stat-box"><span>تبديلات الجولة {{ tm.current_gameweek }}</span><strong>{{ tm.gw_transfers.get(tm.current_gameweek, 0) }}</strong></div>
        <div class="stat-box"><span>الديدلاين</span><strong>{{ "متاح" if tm.is_before_deadline() else "مقفول" }}</strong></div>
      </div>

      <div class="btn-row">
        <form method="post" action="{{ url_for('action_borrow') }}">
          <button type="submit">استلاف تبديلة من الجولة التالية</button>
        </form>
        <form method="post" action="{{ url_for('action_transfer', count=1) }}">
          <button type="submit">تنفيذ 1 تبديل</button>
        </form>
        <form method="post" action="{{ url_for('action_transfer', count=3) }}">
          <button type="submit" class="warn">تنفيذ 3 تبديلات (اختبار -3)</button>
        </form>
        <form method="post" action="{{ url_for('action_toggle_deadline') }}">
          <button type="submit" class="secondary">تبديل حالة الديدلاين (متاح / مقفول)</button>
        </form>
        <form method="post" action="{{ url_for('action_save_report') }}">
          <button type="submit">حفظ التقرير و JSON</button>
        </form>
        <form method="post" action="{{ url_for('action_reset') }}">
          <button type="submit" class="secondary">إعادة ضبط التشكيلة الافتراضية</button>
        </form>
      </div>
    </div>

    <form method="post" action="{{ url_for('update_squad') }}">
      <div class="card">
        <h3>التشكيلة الأساسية (11 لاعب)</h3>
        <table>
          <thead>
            <tr>
              <th>اللاعب</th>
              <th>المركز</th>
              <th>كابتن</th>
              <th>دقائق</th>
              <th>أهداف عادية</th>
              <th>أسيست</th>
              <th>كلين / أهداف مستقبلة</th>
              <th>تصديات</th>
              <th>تدخلات دفاعية</th>
              <th>إنذار / طرد</th>
              <th>نقاطه</th>
            </tr>
          </thead>
          <tbody>
            {% for p in starting_xi %}
            <tr>
              <td>
                <strong>{{ p.name }}</strong>
                {% if p.is_captain %}<span class="cap-badge">C</span>{% endif %}
                {% if p.replaced_by %}<span class="sub-note">بديل تلقائي: {{ p.replaced_by }}</span>{% endif %}
              </td>
              <td>{{ p.normalized_position }}</td>
              <td><input type="radio" name="captain" value="xi_{{ loop.index0 }}" {% if p.is_captain %}checked{% endif %} /></td>
              <td><input type="number" name="xi_minutes_{{ loop.index0 }}" value="{{ p.minutes }}" min="0" max="120" /></td>
              <td><input type="number" name="xi_goals_{{ loop.index0 }}" value="{{ p.regular_goals }}" min="0" max="15" /></td>
              <td><input type="number" name="xi_assists_{{ loop.index0 }}" value="{{ p.assists }}" min="0" max="15" /></td>
              <td><input type="number" name="xi_conceded_{{ loop.index0 }}" value="{{ p.goals_conceded }}" min="0" max="15" /></td>
              <td><input type="number" name="xi_saves_{{ loop.index0 }}" value="{{ p.saves }}" min="0" max="20" /></td>
              <td><input type="number" name="xi_def_{{ loop.index0 }}" value="{{ p.defensive_actions }}" min="0" max="30" /></td>
              <td>
                <input type="number" name="xi_yellow_{{ loop.index0 }}" value="{{ p.yellow_cards }}" min="0" max="2" title="إنذارات" />
                <input type="checkbox" name="xi_red_{{ loop.index0 }}" {% if p.red_card %}checked{% endif %} title="طرد" />
              </td>
              <td><strong>{{ p.total_points }}</strong></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="card">
        <h3>الدكة (4 لاعبين) — يتم الدفع التلقائي عند غياب أساسي (0 دقيقة)</h3>
        <table>
          <thead>
            <tr>
              <th>اللاعب</th>
              <th>المركز</th>
              <th>كابتن</th>
              <th>دقائق</th>
              <th>أهداف عادية</th>
              <th>أسيست</th>
              <th>أهداف مستقبلة</th>
              <th>تصديات</th>
              <th>تدخلات دفاعية</th>
              <th>إنذار / طرد</th>
              <th>نقاطه</th>
            </tr>
          </thead>
          <tbody>
            {% for p in bench_4 %}
            <tr>
              <td>
                <strong>{{ p.name }}</strong>
                {% if p.is_captain %}<span class="cap-badge">C</span>{% endif %}
              </td>
              <td>{{ p.normalized_position }}</td>
              <td><input type="radio" name="captain" value="bench_{{ loop.index0 }}" {% if p.is_captain %}checked{% endif %} /></td>
              <td><input type="number" name="bench_minutes_{{ loop.index0 }}" value="{{ p.minutes }}" min="0" max="120" /></td>
              <td><input type="number" name="bench_goals_{{ loop.index0 }}" value="{{ p.regular_goals }}" min="0" max="15" /></td>
              <td><input type="number" name="bench_assists_{{ loop.index0 }}" value="{{ p.assists }}" min="0" max="15" /></td>
              <td><input type="number" name="bench_conceded_{{ loop.index0 }}" value="{{ p.goals_conceded }}" min="0" max="15" /></td>
              <td><input type="number" name="bench_saves_{{ loop.index0 }}" value="{{ p.saves }}" min="0" max="20" /></td>
              <td><input type="number" name="bench_def_{{ loop.index0 }}" value="{{ p.defensive_actions }}" min="0" max="30" /></td>
              <td>
                <input type="number" name="bench_yellow_{{ loop.index0 }}" value="{{ p.yellow_cards }}" min="0" max="2" />
                <input type="checkbox" name="bench_red_{{ loop.index0 }}" {% if p.red_card %}checked{% endif %} />
              </td>
              <td><strong>{{ p.total_points }}</strong></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>

        <div class="btn-row">
          <button type="submit">حساب النقاط وتحديث التشكيلة</button>
        </div>
      </div>
    </form>
  </div>
</body>
</html>
"""

app = Flask(__name__)


def _int_val(form_data: Dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(form_data.get(key, default))
    except (ValueError, TypeError):
        return default


@app.route("/")
def index() -> str:
    global STATUS_BANNER
    error_msg: Optional[str] = None
    try:
        active_xi, gw_total = resolve_lineup_with_bench(
            STARTING_XI, BENCH_4, TRANSFER_MGR.penalty_points
        )
        players_total = sum(p.total_points for p in active_xi)
    except Exception as exc:
        active_xi = STARTING_XI
        gw_total = 0
        players_total = 0
        error_msg = f"تنبيه في التشكيلة: {exc}"

    return render_template_string(
        HTML_TEMPLATE,
        starting_xi=STARTING_XI,
        bench_4=BENCH_4,
        tm=TRANSFER_MGR,
        gw_total=gw_total,
        players_total=players_total,
        status_banner=STATUS_BANNER,
        error_msg=error_msg,
    )


@app.post("/update-squad")
def update_squad() -> Any:
    global STATUS_BANNER
    form = request.form
    captain_choice = form.get("captain", "xi_5")

    for idx, p in enumerate(STARTING_XI):
        p.minutes = _int_val(form, f"xi_minutes_{idx}", p.minutes)
        p.regular_goals = _int_val(form, f"xi_goals_{idx}", p.regular_goals)
        p.assists = _int_val(form, f"xi_assists_{idx}", p.assists)
        p.goals_conceded = _int_val(form, f"xi_conceded_{idx}", p.goals_conceded)
        p.saves = _int_val(form, f"xi_saves_{idx}", p.saves)
        p.defensive_actions = _int_val(form, f"xi_def_{idx}", p.defensive_actions)
        p.yellow_cards = _int_val(form, f"xi_yellow_{idx}", p.yellow_cards)
        p.red_card = f"xi_red_{idx}" in form
        p.is_captain = (captain_choice == f"xi_{idx}")

    for idx, p in enumerate(BENCH_4):
        p.minutes = _int_val(form, f"bench_minutes_{idx}", p.minutes)
        p.regular_goals = _int_val(form, f"bench_goals_{idx}", p.regular_goals)
        p.assists = _int_val(form, f"bench_assists_{idx}", p.assists)
        p.goals_conceded = _int_val(form, f"bench_conceded_{idx}", p.goals_conceded)
        p.saves = _int_val(form, f"bench_saves_{idx}", p.saves)
        p.defensive_actions = _int_val(form, f"bench_def_{idx}", p.defensive_actions)
        p.yellow_cards = _int_val(form, f"bench_yellow_{idx}", p.yellow_cards)
        p.red_card = f"bench_red_{idx}" in form
        p.is_captain = (captain_choice == f"bench_{idx}")

    STATUS_BANNER = "تم تحديث أرقام اللاعبين وحساب النقاط بنجاح."
    return redirect(url_for("index"))


@app.post("/borrow")
def action_borrow() -> Any:
    global STATUS_BANNER
    _, msg = TRANSFER_MGR.borrow_next_gameweek_transfer()
    STATUS_BANNER = msg
    return redirect(url_for("index"))


@app.post("/transfer/<int:count>")
def action_transfer(count: int) -> Any:
    global STATUS_BANNER
    _, _, msg = TRANSFER_MGR.make_transfer(count=count)
    STATUS_BANNER = msg
    return redirect(url_for("index"))


@app.post("/toggle-deadline")
def action_toggle_deadline() -> Any:
    global STATUS_BANNER
    if TRANSFER_MGR.is_before_deadline():
        TRANSFER_MGR.match_kickoff = datetime.now() + timedelta(minutes=15)
        STATUS_BANNER = "تم قفل الديدلاين (المباراة بعد 15 دقيقة فقط)."
    else:
        TRANSFER_MGR.match_kickoff = datetime.now() + timedelta(hours=3)
        STATUS_BANNER = "تم فتح الديدلاين (المباراة بعد 3 ساعات)."
    return redirect(url_for("index"))


@app.post("/save-report")
def action_save_report() -> Any:
    global STATUS_BANNER
    try:
        active_xi, gw_total = resolve_lineup_with_bench(
            STARTING_XI, BENCH_4, TRANSFER_MGR.penalty_points
        )
        path_str = save_report_and_json(active_xi, gw_total, extra_notes=TRANSFER_MGR.last_message)
        STATUS_BANNER = f"تم حفظ التقرير وملف JSON في: {path_str}"
    except Exception as exc:
        STATUS_BANNER = f"تعذر حفظ التقرير: {exc}"
    return redirect(url_for("index"))


@app.post("/reset")
def action_reset() -> Any:
    global STARTING_XI, BENCH_4, TRANSFER_MGR, STATUS_BANNER
    STARTING_XI, BENCH_4 = build_sample_squad()
    TRANSFER_MGR = TransferManager(
        current_gameweek=10,
        match_kickoff=datetime.now() + timedelta(hours=2),
    )
    STATUS_BANNER = "تمت إعادة ضبط التشكيلة والتبديلات للقيم الافتراضية."
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
