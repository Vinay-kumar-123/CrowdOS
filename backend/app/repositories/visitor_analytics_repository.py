"""
Visitor Analytics Repository — Sprint 14.

Asynchronous MongoDB aggregation repository for:
- Visitor profile analytics & duration distribution
- Gate usage analytics with deterministic tie-breaking
- Day-by-day visitor metrics
- Chronological multi-visit daily timeline
- Venue-wide visitor analytics & new vs returning classification
- Venue-wide daily trend trajectory

All queries strictly enforce venue isolation.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.models.visitor import ensure_utc_datetime

logger = logging.getLogger("crowdos.repositories.visitor_analytics")


class VisitorAnalyticsRepository:
    """
    Direct MongoDB aggregation engine across visitors, visitor_events, and visits collections.
    Strictly venue-isolated.
    """

    def __init__(
        self,
        visitors_collection=None,
        visitor_events_collection=None,
        visits_collection=None,
    ):
        self.visitors_col = visitors_collection
        self.events_col = visitor_events_collection
        self.visits_col = visits_collection

    @property
    def is_available(self) -> bool:
        """True only if all three underlying MongoDB collections are connected."""
        return (
            self.visitors_col is not None
            and self.events_col is not None
            and self.visits_col is not None
        )

    # ========================================================================
    # 1. Visitor Profile & Duration Stats
    # ========================================================================

    async def get_visitor_profile(self, venue_id: str, visitor_id: str) -> Optional[Dict[str, Any]]:
        """Fetch raw visitor profile document scoped by venue_id and visitor_id."""
        if not self.is_available:
            return None
        return await self.visitors_col.find_one({"venue_id": venue_id, "visitor_id": visitor_id})

    async def get_visit_duration_stats(
        self,
        venue_id: str,
        visitor_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate duration metrics for COMPLETED visits only.
        Authoritative source: visits.duration_seconds.
        OPEN visits are strictly excluded from duration stats.
        """
        if not self.is_available:
            return {
                "completed_visits_count": 0,
                "open_visits_excluded_count": 0,
                "total_duration_seconds": 0.0,
                "average_duration_seconds": None,
                "minimum_duration_seconds": None,
                "maximum_duration_seconds": None,
                "median_duration_seconds": None,
            }

        match_base: Dict[str, Any] = {"venue_id": venue_id}
        if visitor_id:
            match_base["visitor_id"] = visitor_id
        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_base["entry_time"] = time_filter

        # Count open visits
        open_match = {**match_base, "status": "OPEN"}
        open_visits_count = await self.visits_col.count_documents(open_match)

        # Aggregate completed visits
        comp_match = {**match_base, "status": "COMPLETED"}
        pipeline = [
            {"$match": comp_match},
            {
                "$group": {
                    "_id": None,
                    "count": {"$sum": 1},
                    "total_dur": {"$sum": "$duration_seconds"},
                    "avg_dur": {"$avg": "$duration_seconds"},
                    "min_dur": {"$min": "$duration_seconds"},
                    "max_dur": {"$max": "$duration_seconds"},
                    "durations": {"$push": "$duration_seconds"},
                }
            },
        ]

        cursor = self.visits_col.aggregate(pipeline)
        docs = await cursor.to_list(length=1)

        if not docs:
            return {
                "completed_visits_count": 0,
                "open_visits_excluded_count": open_visits_count,
                "total_duration_seconds": 0.0,
                "average_duration_seconds": None,
                "minimum_duration_seconds": None,
                "maximum_duration_seconds": None,
                "median_duration_seconds": None,
            }

        doc = docs[0]
        completed_count = doc.get("count", 0)
        total_dur = round(float(doc.get("total_dur", 0.0) or 0.0), 2)
        avg_dur = round(float(doc.get("avg_dur", 0.0)), 2) if doc.get("avg_dur") is not None else None
        min_dur = round(float(doc.get("min_dur", 0.0)), 2) if doc.get("min_dur") is not None else None
        max_dur = round(float(doc.get("max_dur", 0.0)), 2) if doc.get("max_dur") is not None else None

        # Median calculation in Python from durations list
        durations = [float(d) for d in doc.get("durations", []) if d is not None]
        durations.sort()
        median_dur: Optional[float] = None
        if durations:
            n = len(durations)
            if n % 2 == 1:
                median_dur = round(durations[n // 2], 2)
            else:
                median_dur = round((durations[n // 2 - 1] + durations[n // 2]) / 2.0, 2)

        return {
            "completed_visits_count": completed_count,
            "open_visits_excluded_count": open_visits_count,
            "total_duration_seconds": total_dur,
            "average_duration_seconds": avg_dur,
            "minimum_duration_seconds": min_dur,
            "maximum_duration_seconds": max_dur,
            "median_duration_seconds": median_dur,
        }

    async def get_visitor_visit_days_and_bounds(
        self, venue_id: str, visitor_id: str
    ) -> Dict[str, Any]:
        """Aggregate unique visit days and first/last visit bounds from visits collection."""
        if not self.is_available:
            return {
                "unique_visit_days": 0,
                "first_visit_at": None,
                "last_visit_at": None,
                "total_visits_in_collection": 0,
                "completed_visits": 0,
                "open_visits": 0,
            }

        pipeline = [
            {"$match": {"venue_id": venue_id, "visitor_id": visitor_id}},
            {
                "$group": {
                    "_id": None,
                    "first_visit": {"$min": "$entry_time"},
                    "last_visit": {"$max": "$entry_time"},
                    "days": {
                        "$addToSet": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$entry_time"}
                        }
                    },
                    "total_visits": {"$sum": 1},
                    "completed": {
                        "$sum": {"$cond": [{"$eq": ["$status", "COMPLETED"]}, 1, 0]}
                    },
                    "open": {"$sum": {"$cond": [{"$eq": ["$status", "OPEN"]}, 1, 0]}},
                }
            },
        ]

        cursor = self.visits_col.aggregate(pipeline)
        docs = await cursor.to_list(length=1)

        if not docs:
            return {
                "unique_visit_days": 0,
                "first_visit_at": None,
                "last_visit_at": None,
                "total_visits_in_collection": 0,
                "completed_visits": 0,
                "open_visits": 0,
            }

        doc = docs[0]
        days_list = doc.get("days", [])
        return {
            "unique_visit_days": len(days_list),
            "first_visit_at": doc.get("first_visit"),
            "last_visit_at": doc.get("last_visit"),
            "total_visits_in_collection": doc.get("total_visits", 0),
            "completed_visits": doc.get("completed", 0),
            "open_visits": doc.get("open", 0),
        }

    # ========================================================================
    # 2. Gate Analytics
    # ========================================================================

    async def get_gate_usage_stats(
        self,
        venue_id: str,
        visitor_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate entry and exit gate usage from visitor_events.
        Calculates exact counts, percentages, and identifies top gates.
        Ties are broken deterministically by sorting (count DESC, gate_id ASC).
        """
        if not self.is_available:
            return {
                "total_entries": 0,
                "total_exits": 0,
                "entry_gates": [],
                "exit_gates": [],
                "most_used_entry_gate": None,
                "most_used_exit_gate": None,
            }

        match_q: Dict[str, Any] = {"venue_id": venue_id}
        if visitor_id:
            match_q["visitor_id"] = visitor_id
        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_q["timestamp"] = time_filter

        pipeline = [
            {"$match": match_q},
            {
                "$group": {
                    "_id": {"gate_id": "$gate_id", "event_type": "$event_type"},
                    "count": {"$sum": 1},
                }
            },
        ]

        cursor = self.events_col.aggregate(pipeline)
        docs = await cursor.to_list(length=500)

        entry_dict: Dict[str, int] = {}
        exit_dict: Dict[str, int] = {}

        for doc in docs:
            group_key = doc.get("_id", {})
            gate_id = group_key.get("gate_id")
            event_type = group_key.get("event_type")
            cnt = doc.get("count", 0)

            if not gate_id:
                continue

            if event_type == "ENTRY":
                entry_dict[gate_id] = entry_dict.get(gate_id, 0) + cnt
            elif event_type == "EXIT":
                exit_dict[gate_id] = exit_dict.get(gate_id, 0) + cnt

        total_entries = sum(entry_dict.values())
        total_exits = sum(exit_dict.values())

        # Sort with deterministic tie-breaking: count DESC, then gate_id ASC
        sorted_entries = sorted(entry_dict.items(), key=lambda x: (-x[1], x[0]))
        sorted_exits = sorted(exit_dict.items(), key=lambda x: (-x[1], x[0]))

        entry_gates = [
            {
                "gate_id": gid,
                "count": cnt,
                "percentage": round((cnt / total_entries * 100.0), 2) if total_entries > 0 else 0.0,
            }
            for gid, cnt in sorted_entries
        ]
        exit_gates = [
            {
                "gate_id": gid,
                "count": cnt,
                "percentage": round((cnt / total_exits * 100.0), 2) if total_exits > 0 else 0.0,
            }
            for gid, cnt in sorted_exits
        ]

        most_used_entry = sorted_entries[0][0] if sorted_entries else None
        most_used_exit = sorted_exits[0][0] if sorted_exits else None

        return {
            "total_entries": total_entries,
            "total_exits": total_exits,
            "entry_gates": entry_gates,
            "exit_gates": exit_gates,
            "most_used_entry_gate": most_used_entry,
            "most_used_exit_gate": most_used_exit,
        }

    # ========================================================================
    # 3. Daily Visitor Analytics
    # ========================================================================

    async def get_visitor_daily_breakdown(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate day-by-day metrics for a visitor.
        Returns chronological list of UTC days with entries, exits, visits, and durations.
        """
        if not self.is_available:
            return []

        match_events: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}
        match_visits: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_events["timestamp"] = time_filter
            match_visits["entry_time"] = time_filter

        # Aggregate events by day and event_type
        pipeline_ev = [
            {"$match": match_events},
            {
                "$group": {
                    "_id": {
                        "date": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                        },
                        "event_type": "$event_type",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]
        cursor_ev = self.events_col.aggregate(pipeline_ev)
        docs_ev = await cursor_ev.to_list(length=1000)

        # Aggregate visits by day
        pipeline_vis = [
            {"$match": match_visits},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$entry_time"}
                    },
                    "total_started": {"$sum": 1},
                    "completed": {
                        "$sum": {"$cond": [{"$eq": ["$status", "COMPLETED"]}, 1, 0]}
                    },
                    "open": {"$sum": {"$cond": [{"$eq": ["$status", "OPEN"]}, 1, 0]}},
                    "completed_durations": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$status", "COMPLETED"]},
                                "$duration_seconds",
                                "$$REMOVE",
                            ]
                        }
                    },
                }
            },
        ]
        cursor_vis = self.visits_col.aggregate(pipeline_vis)
        docs_vis = await cursor_vis.to_list(length=1000)

        days_dict: Dict[str, Dict[str, Any]] = {}

        for doc in docs_ev:
            d_str = doc["_id"]["date"]
            ev_type = doc["_id"]["event_type"]
            cnt = doc.get("count", 0)
            if d_str not in days_dict:
                days_dict[d_str] = {
                    "date": d_str,
                    "total_entries": 0,
                    "total_exits": 0,
                    "total_visits_started": 0,
                    "completed_visits": 0,
                    "open_visits": 0,
                    "durations": [],
                }
            if ev_type == "ENTRY":
                days_dict[d_str]["total_entries"] += cnt
            elif ev_type == "EXIT":
                days_dict[d_str]["total_exits"] += cnt

        for doc in docs_vis:
            d_str = doc["_id"]
            if d_str not in days_dict:
                days_dict[d_str] = {
                    "date": d_str,
                    "total_entries": 0,
                    "total_exits": 0,
                    "total_visits_started": 0,
                    "completed_visits": 0,
                    "open_visits": 0,
                    "durations": [],
                }
            days_dict[d_str]["total_visits_started"] += doc.get("total_started", 0)
            days_dict[d_str]["completed_visits"] += doc.get("completed", 0)
            days_dict[d_str]["open_visits"] += doc.get("open", 0)
            days_dict[d_str]["durations"].extend(
                [float(d) for d in doc.get("completed_durations", []) if d is not None]
            )

        # Format and calculate averages
        result = []
        for d_str in sorted(days_dict.keys()):
            item = days_dict[d_str]
            durations = item["durations"]
            tot_dur = round(sum(durations), 2)
            avg_dur = round(tot_dur / len(durations), 2) if durations else None
            result.append({
                "date": d_str,
                "total_entries": item["total_entries"],
                "total_exits": item["total_exits"],
                "total_visits_started": item["total_visits_started"],
                "completed_visits": item["completed_visits"],
                "open_visits": item["open_visits"],
                "average_visit_duration_seconds": avg_dur,
                "total_visit_duration_seconds": tot_dur,
            })

        return result

    # ========================================================================
    # 4. Visitor Daily Timeline (Multiple Visits Preserved)
    # ========================================================================

    async def get_visitor_timeline(
        self,
        venue_id: str,
        visitor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Chronological daily timeline preserving distinct visits per day.
        Does not collapse multiple visits on the same day.
        """
        if not self.is_available:
            return []

        match_events: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}
        match_visits: Dict[str, Any] = {"venue_id": venue_id, "visitor_id": visitor_id}

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_events["timestamp"] = time_filter
            match_visits["entry_time"] = time_filter

        # Fetch events and visits sorted chronologically
        events_cursor = self.events_col.find(match_events).sort("timestamp", 1)
        events = await events_cursor.to_list(length=2000)

        visits_cursor = self.visits_col.find(match_visits).sort("entry_time", 1)
        visits = await visits_cursor.to_list(length=2000)

        days_map: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            ts: datetime = ensure_utc_datetime(ev["timestamp"])
            d_str = ts.strftime("%Y-%m-%d")
            iso_ts = ts.isoformat()
            ev_type = ev["event_type"]

            if d_str not in days_map:
                days_map[d_str] = {
                    "date": d_str,
                    "entries_count": 0,
                    "exits_count": 0,
                    "visits_count": 0,
                    "total_duration_seconds": 0.0,
                    "first_event_time": iso_ts,
                    "last_event_time": iso_ts,
                    "visits": [],
                }

            node = days_map[d_str]
            if ev_type == "ENTRY":
                node["entries_count"] += 1
            elif ev_type == "EXIT":
                node["exits_count"] += 1

            if iso_ts < node["first_event_time"]:
                node["first_event_time"] = iso_ts
            if iso_ts > node["last_event_time"]:
                node["last_event_time"] = iso_ts

        for vis in visits:
            ent: datetime = ensure_utc_datetime(vis["entry_time"])
            d_str = ent.strftime("%Y-%m-%d")
            ext: Optional[datetime] = ensure_utc_datetime(vis.get("exit_time"))
            dur = vis.get("duration_seconds")
            status = vis.get("status", "OPEN")

            if d_str not in days_map:
                days_map[d_str] = {
                    "date": d_str,
                    "entries_count": 0,
                    "exits_count": 0,
                    "visits_count": 0,
                    "total_duration_seconds": 0.0,
                    "first_event_time": ent.isoformat(),
                    "last_event_time": ent.isoformat(),
                    "visits": [],
                }

            node = days_map[d_str]
            node["visits_count"] += 1
            if dur is not None and status == "COMPLETED":
                node["total_duration_seconds"] = round(node["total_duration_seconds"] + float(dur), 2)

            node["visits"].append({
                "visit_id": vis["visit_id"],
                "entry_time": ent.isoformat(),
                "exit_time": ext.isoformat() if ext else None,
                "entry_gate": vis["entry_gate"],
                "exit_gate": vis.get("exit_gate"),
                "duration_seconds": dur,
                "status": status,
            })

        timeline = []
        for d_str in sorted(days_map.keys()):
            timeline.append(days_map[d_str])

        return timeline

    # ========================================================================
    # 5. Venue-Level Analytics & New vs Returning Classification
    # ========================================================================

    async def get_venue_visitor_analytics(
        self,
        venue_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate venue-level visitor analytics over a date range.
        Calculates:
        - unique_visitors active in range
        - new_visitors: first-ever historical recorded event falls in range
        - returning_visitors: active in range, but first-ever recorded event was before start_time
        - total_entries, total_exits, total_visits, completed_visits, open_visits
        - duration metrics on completed visits
        """
        if not self.is_available:
            return {
                "venue_id": venue_id,
                "unique_visitors": 0,
                "new_visitors": 0,
                "returning_visitors": 0,
                "total_entries": 0,
                "total_exits": 0,
                "total_visits": 0,
                "completed_visits": 0,
                "open_visits": 0,
                "average_visit_duration_seconds": None,
                "minimum_visit_duration_seconds": None,
                "maximum_visit_duration_seconds": None,
                "total_visit_duration_seconds": 0.0,
            }

        match_events: Dict[str, Any] = {"venue_id": venue_id}
        match_visits: Dict[str, Any] = {"venue_id": venue_id}

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_events["timestamp"] = time_filter
            match_visits["entry_time"] = time_filter

        # 1. Unique visitors active in the range (from events collection)
        active_visitor_ids: List[str] = await self.events_col.distinct("visitor_id", match_events)
        unique_visitors_count = len(active_visitor_ids)

        # 2. Classify new vs returning based on historical first_seen_at
        new_visitors_count = 0
        returning_visitors_count = 0

        if active_visitor_ids:
            # Query visitors collection for active visitor documents
            vis_cursor = self.visitors_col.find(
                {"venue_id": venue_id, "visitor_id": {"$in": active_visitor_ids}}
            )
            visitor_docs = await vis_cursor.to_list(length=len(active_visitor_ids) + 50)
            for vdoc in visitor_docs:
                first_seen = ensure_utc_datetime(vdoc.get("first_seen_at"))
                if not first_seen:
                    new_visitors_count += 1
                elif start_time and first_seen < start_time:
                    returning_visitors_count += 1
                else:
                    new_visitors_count += 1

        # 3. Aggregate entry and exit counts from visitor_events
        pipeline_ev = [
            {"$match": match_events},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]
        ev_docs = await self.events_col.aggregate(pipeline_ev).to_list(length=10)
        entries_cnt = 0
        exits_cnt = 0
        for doc in ev_docs:
            if doc["_id"] == "ENTRY":
                entries_cnt = doc.get("count", 0)
            elif doc["_id"] == "EXIT":
                exits_cnt = doc.get("count", 0)

        # 4. Aggregate visits and duration stats from visits collection
        pipeline_vis = [
            {"$match": match_visits},
            {
                "$group": {
                    "_id": None,
                    "total_visits": {"$sum": 1},
                    "completed_visits": {
                        "$sum": {"$cond": [{"$eq": ["$status", "COMPLETED"]}, 1, 0]}
                    },
                    "open_visits": {
                        "$sum": {"$cond": [{"$eq": ["$status", "OPEN"]}, 1, 0]}
                    },
                    "completed_durations": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$status", "COMPLETED"]},
                                "$duration_seconds",
                                "$$REMOVE",
                            ]
                        }
                    },
                }
            },
        ]
        vis_docs = await self.visits_col.aggregate(pipeline_vis).to_list(length=1)

        total_visits = 0
        completed_visits = 0
        open_visits = 0
        total_duration = 0.0
        avg_duration = None
        min_duration = None
        max_duration = None

        if vis_docs:
            v_doc = vis_docs[0]
            total_visits = v_doc.get("total_visits", 0)
            completed_visits = v_doc.get("completed_visits", 0)
            open_visits = v_doc.get("open_visits", 0)
            durations = [
                float(d) for d in v_doc.get("completed_durations", []) if d is not None
            ]
            if durations:
                total_duration = round(sum(durations), 2)
                avg_duration = round(total_duration / len(durations), 2)
                min_duration = round(min(durations), 2)
                max_duration = round(max(durations), 2)

        return {
            "venue_id": venue_id,
            "unique_visitors": unique_visitors_count,
            "new_visitors": new_visitors_count,
            "returning_visitors": returning_visitors_count,
            "total_entries": entries_cnt,
            "total_exits": exits_cnt,
            "total_visits": total_visits,
            "completed_visits": completed_visits,
            "open_visits": open_visits,
            "average_visit_duration_seconds": avg_duration,
            "minimum_visit_duration_seconds": min_duration,
            "maximum_visit_duration_seconds": max_duration,
            "total_visit_duration_seconds": total_duration,
        }

    # ========================================================================
    # 6. Venue Daily Trends
    # ========================================================================

    async def get_venue_daily_trends(
        self,
        venue_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate day-by-day trends across the entire venue.
        Returns chronological list of UTC dates with:
        unique_visitors, total_entries, total_exits, total_visits, completed_visits,
        open_visits, average_duration, total_duration.
        """
        if not self.is_available:
            return []

        match_events: Dict[str, Any] = {"venue_id": venue_id}
        match_visits: Dict[str, Any] = {"venue_id": venue_id}

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_events["timestamp"] = time_filter
            match_visits["entry_time"] = time_filter

        # 1. Aggregate events by date
        pipeline_ev = [
            {"$match": match_events},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "visitors": {"$addToSet": "$visitor_id"},
                    "entries": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", "ENTRY"]}, 1, 0]}
                    },
                    "exits": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", "EXIT"]}, 1, 0]}
                    },
                }
            },
        ]
        cursor_ev = self.events_col.aggregate(pipeline_ev)
        docs_ev = await cursor_ev.to_list(length=1000)

        # 2. Aggregate visits by date
        pipeline_vis = [
            {"$match": match_visits},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$entry_time"}
                    },
                    "total_visits": {"$sum": 1},
                    "completed_visits": {
                        "$sum": {"$cond": [{"$eq": ["$status", "COMPLETED"]}, 1, 0]}
                    },
                    "open_visits": {
                        "$sum": {"$cond": [{"$eq": ["$status", "OPEN"]}, 1, 0]}
                    },
                    "completed_durations": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$status", "COMPLETED"]},
                                "$duration_seconds",
                                "$$REMOVE",
                            ]
                        }
                    },
                }
            },
        ]
        cursor_vis = self.visits_col.aggregate(pipeline_vis)
        docs_vis = await cursor_vis.to_list(length=1000)

        days_dict: Dict[str, Dict[str, Any]] = {}

        for doc in docs_ev:
            d_str = doc["_id"]
            if d_str not in days_dict:
                days_dict[d_str] = {
                    "date": d_str,
                    "unique_visitors": len(doc.get("visitors", [])),
                    "total_entries": doc.get("entries", 0),
                    "total_exits": doc.get("exits", 0),
                    "total_visits": 0,
                    "completed_visits": 0,
                    "open_visits": 0,
                    "durations": [],
                }
            else:
                days_dict[d_str]["unique_visitors"] = len(doc.get("visitors", []))
                days_dict[d_str]["total_entries"] = doc.get("entries", 0)
                days_dict[d_str]["total_exits"] = doc.get("exits", 0)

        for doc in docs_vis:
            d_str = doc["_id"]
            if d_str not in days_dict:
                days_dict[d_str] = {
                    "date": d_str,
                    "unique_visitors": 0,
                    "total_entries": 0,
                    "total_exits": 0,
                    "total_visits": doc.get("total_visits", 0),
                    "completed_visits": doc.get("completed_visits", 0),
                    "open_visits": doc.get("open_visits", 0),
                    "durations": [
                        float(d)
                        for d in doc.get("completed_durations", [])
                        if d is not None
                    ],
                }
            else:
                days_dict[d_str]["total_visits"] = doc.get("total_visits", 0)
                days_dict[d_str]["completed_visits"] = doc.get("completed_visits", 0)
                days_dict[d_str]["open_visits"] = doc.get("open_visits", 0)
                days_dict[d_str]["durations"].extend(
                    [
                        float(d)
                        for d in doc.get("completed_durations", [])
                        if d is not None
                    ]
                )

        trends = []
        for d_str in sorted(days_dict.keys()):
            item = days_dict[d_str]
            durations = item["durations"]
            tot_dur = round(sum(durations), 2)
            avg_dur = round(tot_dur / len(durations), 2) if durations else None
            trends.append({
                "date": d_str,
                "unique_visitors": item["unique_visitors"],
                "total_entries": item["total_entries"],
                "total_exits": item["total_exits"],
                "total_visits": item["total_visits"],
                "completed_visits": item["completed_visits"],
                "open_visits": item["open_visits"],
                "average_visit_duration_seconds": avg_dur,
                "total_visit_duration_seconds": tot_dur,
            })

        return trends
