"""
API Relay Monitor - 评分与风险评估系统
提供加权评分、风险等级计算和价格比较功能
"""

from typing import Optional, Dict, Any


class Scorer:
    """评分与风险评估引擎"""

    # 评分权重配置
    WEIGHTS = {
        "stability": 0.40,      # 稳定性权重 40%
        "price": 0.30,          # 价格权重 30%
        "update_speed": 0.20,   # 更新速度权重 20%
        "community": 0.10,      # 社区口碑权重 10%
    }

    # 风险阈值
    RISK_THRESHOLDS = {
        "high_score": 7.0,      # 高分阈值
        "medium_score": 4.0,    # 中分阈值
        "high_multiplier": 1.5, # 高倍率阈值（相对官方价格）
        "low_multiplier": 0.1,  # 异常低价阈值
    }

    def calculate_overall_score(
        self,
        stability: float = 5.0,
        price: float = 5.0,
        update_speed: float = 5.0,
        community: float = 5.0,
    ) -> float:
        """
        计算综合评分
        使用加权平均：稳定性40% + 价格30% + 更新速度20% + 社区10%
        """
        # 确保各分项在 1-10 范围内
        stability = max(1.0, min(10.0, float(stability)))
        price = max(1.0, min(10.0, float(price)))
        update_speed = max(1.0, min(10.0, float(update_speed)))
        community = max(1.0, min(10.0, float(community)))

        overall = (
            stability * self.WEIGHTS["stability"]
            + price * self.WEIGHTS["price"]
            + update_speed * self.WEIGHTS["update_speed"]
            + community * self.WEIGHTS["community"]
        )

        return round(overall, 2)

    def calculate_risk_level(
        self,
        overall_score: float,
        price_multiplier: Optional[float] = None,
        relay_type: Optional[str] = None,
        has_negative_feedback: bool = False,
    ) -> str:
        """
        计算风险等级
        返回: low / medium / high
        """
        risk_score = 0  # 风险积分，越高越危险

        # 1. 基于综合评分
        if overall_score >= self.RISK_THRESHOLDS["high_score"]:
            risk_score -= 2  # 高分降低风险
        elif overall_score >= self.RISK_THRESHOLDS["medium_score"]:
            risk_score += 0  # 中等分数不变
        else:
            risk_score += 2  # 低分增加风险

        # 2. 基于价格倍率
        if price_multiplier is not None:
            if price_multiplier <= self.RISK_THRESHOLDS["low_multiplier"]:
                risk_score += 3  # 异常低价，高风险
            elif price_multiplier > self.RISK_THRESHOLDS["high_multiplier"]:
                risk_score += 1  # 高倍率，略高风险
            elif 0.5 <= price_multiplier <= 1.2:
                risk_score -= 1  # 合理价格，降低风险

        # 3. 基于中转类型
        type_risk = {
            "官转": -1,      # 官方转售风险最低
            "聚合": 0,       # 聚合类中等
            "Bedrock": 0,    # Bedrock 中等
            "逆向": 2,       # 逆向工程风险最高
        }
        risk_score += type_risk.get(relay_type, 0)

        # 4. 社区负面反馈
        if has_negative_feedback:
            risk_score += 2

        # 判定风险等级
        if risk_score >= 3:
            return "high"
        elif risk_score >= 1:
            return "medium"
        else:
            return "low"

    def compare_prices(
        self,
        sites_prices: list,
        official_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        价格比较分析
        sites_prices: [{"name": "xxx", "multiplier": 0.8, "price_per_1k": 0.01}, ...]
        official_price: 官方价格（每1K token）
        """
        if not sites_prices:
            return {"error": "无价格数据"}

        # 排序
        sorted_by_price = sorted(
            sites_prices,
            key=lambda x: x.get("price_per_1k", float("inf")) or float("inf"),
        )

        cheapest = sorted_by_price[0] if sorted_by_price else None
        most_expensive = sorted_by_price[-1] if sorted_by_price else None

        result = {
            "cheapest": cheapest,
            "most_expensive": most_expensive,
            "price_range": {
                "min": cheapest.get("price_per_1k") if cheapest else None,
                "max": most_expensive.get("price_per_1k") if most_expensive else None,
            },
            "avg_multiplier": None,
            "savings_vs_official": None,
        }

        # 计算平均倍率
        multipliers = [
            s.get("multiplier") for s in sites_prices
            if s.get("multiplier") is not None
        ]
        if multipliers:
            result["avg_multiplier"] = round(sum(multipliers) / len(multipliers), 4)

        # 与官方价格比较
        if official_price and cheapest and cheapest.get("price_per_1k"):
            savings = ((official_price - cheapest["price_per_1k"]) / official_price) * 100
            result["savings_vs_official"] = round(savings, 2)

        return result

    def get_score_breakdown(
        self,
        stability: float,
        price: float,
        update_speed: float,
        community: float,
    ) -> Dict[str, Any]:
        """
        获取评分详细分解
        """
        overall = self.calculate_overall_score(stability, price, update_speed, community)

        return {
            "overall_score": overall,
            "breakdown": {
                "stability": {
                    "score": stability,
                    "weight": self.WEIGHTS["stability"],
                    "weighted": round(stability * self.WEIGHTS["stability"], 2),
                },
                "price": {
                    "score": price,
                    "weight": self.WEIGHTS["price"],
                    "weighted": round(price * self.WEIGHTS["price"], 2),
                },
                "update_speed": {
                    "score": update_speed,
                    "weight": self.WEIGHTS["update_speed"],
                    "weighted": round(update_speed * self.WEIGHTS["update_speed"], 2),
                },
                "community": {
                    "score": community,
                    "weight": self.WEIGHTS["community"],
                    "weighted": round(community * self.WEIGHTS["community"], 2),
                },
            },
            "grade": self._score_to_grade(overall),
        }

    def _score_to_grade(self, score: float) -> str:
        """将分数转换为等级"""
        if score >= 8.0:
            return "优秀"
        elif score >= 6.5:
            return "良好"
        elif score >= 5.0:
            return "一般"
        elif score >= 3.0:
            return "较差"
        else:
            return "极差"
