RESOURCES: dict[str, list[dict[str, str]]] = {
    "architect": [
        # Well-Architected Framework — pillar overview pages
        {"url": "https://cloud.google.com/architecture/framework/operational-excellence", "filename": "waf-operational-excellence.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security", "filename": "waf-security.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability", "filename": "waf-reliability.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/cost-optimization", "filename": "waf-cost-optimization.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/performance-optimization", "filename": "waf-performance-optimization.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/system-design", "filename": "waf-system-design.txt", "type": "html"},

        # WAF Operational Excellence sub-pages
        {"url": "https://cloud.google.com/architecture/framework/operational-excellence/automate-and-manage-change", "filename": "waf-opex-automate-manage-change.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/operational-excellence/continuously-improve-and-innovate", "filename": "waf-opex-continuously-improve.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/operational-excellence/manage-and-optimize-cloud-resources", "filename": "waf-opex-manage-optimize-resources.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/operational-excellence/manage-incidents-and-problems", "filename": "waf-opex-manage-incidents.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/operational-excellence/operational-readiness-and-performance-using-cloudops", "filename": "waf-opex-operational-readiness.txt", "type": "html"},

        # WAF Security sub-pages
        {"url": "https://cloud.google.com/architecture/framework/security/shared-responsibility-shared-fate", "filename": "waf-sec-shared-responsibility.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/implement-security-by-design", "filename": "waf-sec-security-by-design.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/implement-zero-trust", "filename": "waf-sec-zero-trust.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/implement-shift-left-security", "filename": "waf-sec-shift-left.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/implement-preemptive-cyber-defense", "filename": "waf-sec-preemptive-defense.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/meet-regulatory-compliance-and-privacy-needs", "filename": "waf-sec-compliance-privacy.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/use-ai-for-security", "filename": "waf-sec-ai-for-security.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/security/use-ai-securely-and-responsibly", "filename": "waf-sec-ai-securely.txt", "type": "html"},

        # WAF Reliability sub-pages
        {"url": "https://cloud.google.com/architecture/framework/reliability/define-reliability-based-on-user-experience-goals", "filename": "waf-rel-define-reliability.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/set-targets", "filename": "waf-rel-set-targets.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/build-highly-available-systems", "filename": "waf-rel-high-availability.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/horizontal-scalability", "filename": "waf-rel-horizontal-scalability.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/graceful-degradation", "filename": "waf-rel-graceful-degradation.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/observability", "filename": "waf-rel-observability.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/perform-testing-for-recovery-from-failures", "filename": "waf-rel-test-recovery-failures.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/perform-testing-for-recovery-from-data-loss", "filename": "waf-rel-test-recovery-data-loss.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/reliability/conduct-postmortems", "filename": "waf-rel-postmortems.txt", "type": "html"},

        # WAF Cost Optimization sub-pages
        {"url": "https://cloud.google.com/architecture/framework/cost-optimization/align-cloud-spending-business-value", "filename": "waf-cost-align-spending.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/cost-optimization/foster-culture-cost-awareness", "filename": "waf-cost-culture-awareness.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/cost-optimization/optimize-resource-usage", "filename": "waf-cost-optimize-resources.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/cost-optimization/optimize-continuously", "filename": "waf-cost-optimize-continuously.txt", "type": "html"},

        # WAF Performance Optimization sub-pages
        {"url": "https://cloud.google.com/architecture/framework/performance-optimization/plan-resource-allocation", "filename": "waf-perf-plan-resources.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/performance-optimization/promote-modular-design", "filename": "waf-perf-modular-design.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/performance-optimization/elasticity", "filename": "waf-perf-elasticity.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/framework/performance-optimization/continuously-monitor-and-improve-performance", "filename": "waf-perf-monitor-improve.txt", "type": "html"},

        # Architecture Center — key solution guides
        {"url": "https://cloud.google.com/architecture/hybrid-and-multi-cloud-architecture-patterns", "filename": "arch-hybrid-multicloud-patterns.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/dr-scenarios-planning-guide", "filename": "arch-disaster-recovery-planning.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/best-practices-vpc-design", "filename": "arch-vpc-design-best-practices.txt", "type": "html"},
        {"url": "https://cloud.google.com/kubernetes-engine/docs/best-practices", "filename": "arch-gke-best-practices.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/migration-to-gcp-getting-started", "filename": "arch-migration-guide.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/landing-zones", "filename": "arch-landing-zones.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/security-foundations", "filename": "arch-security-foundations.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/devops", "filename": "arch-devops.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/identity", "filename": "arch-identity.txt", "type": "html"},
        {"url": "https://cloud.google.com/architecture/networking", "filename": "arch-networking.txt", "type": "html"},
        {"url": "https://cloud.google.com/docs/enterprise/best-practices-for-enterprise-organizations", "filename": "arch-enterprise-best-practices.txt", "type": "html"},

        # Product best practices
        {"url": "https://cloud.google.com/storage/docs/best-practices", "filename": "prod-cloud-storage-best-practices.txt", "type": "html"},
        {"url": "https://cloud.google.com/bigquery/docs/best-practices-performance-overview", "filename": "prod-bigquery-best-practices.txt", "type": "html"},
        {"url": "https://cloud.google.com/sql/docs/mysql/best-practices", "filename": "prod-cloud-sql-best-practices.txt", "type": "html"},
        {"url": "https://cloud.google.com/iam/docs/overview", "filename": "prod-iam-overview.txt", "type": "html"},
    ],
}


def get_exam_resources(exam: str) -> list[dict[str, str]]:
    if exam not in RESOURCES:
        raise KeyError(exam)
    return RESOURCES[exam]


def list_exams() -> list[str]:
    return list(RESOURCES.keys())
