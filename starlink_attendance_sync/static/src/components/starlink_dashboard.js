/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class StarlinkDashboard extends Component {
    static template = "starlink_attendance_sync.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            kpis: {
                orphan_out: 0,
                duplicate_in: 0,
                bad_duration: 0,
                employee_not_mapped: 0,
                missing_checkout: 0,
                resolved: 0,
                pending: 0,
                total: 0,
                logs_paired: 0,
                logs_pending: 0,
                logs_total: 0,
            },
        });

        onWillStart(async () => {
            await this.loadKpis();
        });
    }

    async loadKpis() {
        this.state.loading = true;
        try {
            const kpis = await this.orm.call(
                "starlink.punch.exception",
                "get_dashboard_kpis",
                []
            );
            this.state.kpis = kpis;
        } finally {
            this.state.loading = false;
        }
    }

    async openExceptionFilter(issueType, resolved) {
        const action = await this.orm.call(
            "starlink.punch.exception",
            "action_open_filtered",
            [],
            { issue_type: issueType, resolved: resolved }
        );
        this.action.doAction(action);
    }

    async onClickReprocess() {
        // Public wrapper — _cron_live_refresh would be blocked by the
        // remote-call security check on private methods.
        await this.orm.call(
            "starlink.sync.engine",
            "action_run_live_refresh",
            []
        );
        this.notification.add(_t("Reprocess complete."), { type: "success" });
        await this.loadKpis();
    }

    async onClickReconcile() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Reconcile Last 30 Days"),
            res_model: "starlink.reconcile.wizard",
            view_mode: "form",
            target: "new",
            views: [[false, "form"]],
        });
    }

    async onClickRetrySelected() {
        // Open the exception list filtered to unresolved so the user can
        // tick rows and use the Retry button.
        await this.openExceptionFilter(false, false);
    }
}

registry.category("actions").add(
    "starlink_attendance_sync.dashboard",
    StarlinkDashboard
);
