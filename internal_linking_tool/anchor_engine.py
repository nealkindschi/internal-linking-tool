"""Anchor Text Engine: impression-weighted anchor text suggestions."""

import math
from internal_linking_tool.gsc_client import build_impression_weighted_keywords


class AnchorEngine:
    def build_anchor_list(self, queries):
        return build_impression_weighted_keywords(queries)

    def get_variations(self, keyword):
        words = keyword.lower().split()
        variations = [keyword]
        if len(words) > 1:
            variations.append(" ".join(words[:-1]))
        if len(words) > 1:
            variations.append(" ".join(words[1:]))
        if keyword.endswith("s") and not keyword.endswith("ss"):
            variations.append(keyword[:-1])
        seen = set()
        result = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result

    def enrich_opportunities(self, opportunities, queries):
        if not queries:
            return opportunities
        anchors = self.build_anchor_list(queries)
        if not anchors:
            return opportunities
        anchor_map = {a["keyword"].lower(): a for a in anchors}
        for opp in opportunities:
            for match in opp.get("matches", []):
                kw = match.get("keyword", "").lower()
                anchor_data = anchor_map.get(kw)
                if anchor_data:
                    match["anchor_text"] = anchor_data["keyword"]
                    match["impression_share"] = anchor_data["impression_share"]
                    match["variations"] = self.get_variations(anchor_data["keyword"])
        return opportunities


def distribute_anchors(opportunities, keywords):
    if not keywords or not opportunities:
        return opportunities
    total_opps = len(opportunities)
    result = []
    targets = {}
    cumulative = 0
    for kw in keywords:
        count = math.ceil(total_opps * kw["impression_share"])
        targets[kw["keyword"]] = min(count, total_opps - cumulative)
        cumulative += targets[kw["keyword"]]
    opp_index = 0
    for kw_keyword, target_count in targets.items():
        for _ in range(target_count):
            if opp_index < len(opportunities):
                opp = dict(opportunities[opp_index])
                for match in opp.get("matches", []):
                    match["keyword"] = kw_keyword
                    match["anchor_text"] = kw_keyword
                result.append(opp)
                opp_index += 1
    while opp_index < len(opportunities):
        result.append(dict(opportunities[opp_index]))
        opp_index += 1
    return result
