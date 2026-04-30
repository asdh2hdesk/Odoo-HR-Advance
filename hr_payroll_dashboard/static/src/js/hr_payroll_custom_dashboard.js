/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class HrPayrollDashboard extends Component {
    static template = "hr_payroll_dashboard.HrPayrollDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this._chartInstances = {};
        const now = new Date();
        const pad = n => String(n).padStart(2, '0');
        const firstOfMonth = `${now.getFullYear()}-${pad(now.getMonth()+1)}-01`;
        const lastOfMonth = new Date(now.getFullYear(), now.getMonth()+1, 0);
        const lastOfMonthStr = `${lastOfMonth.getFullYear()}-${pad(lastOfMonth.getMonth()+1)}-${pad(lastOfMonth.getDate())}`;

        this.state = useState({
            loading: true,
            data: this._emptyData(),
            dateFrom: firstOfMonth,      // ← NEW
            dateTo: lastOfMonthStr,
            deptSlices: [],
            today: new Date().toLocaleDateString("en-IN", {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
            }),
            month: new Date().toLocaleDateString("en-IN", {
                month: "long",
                year: "numeric",
            }),
            month: now.toLocaleDateString("en-IN", { month: "long", year: "numeric" }),
        });

        onMounted(() => this.loadData());
    }

    // ── Empty/safe default so template never crashes on undefined ──────────
    _emptyData() {
        return {
            attendance_salary: {
                records: [],
                total_attendance_salary: 0,
                total_gross_salary: 0,
                currency: "₹",
            },
            actual_payout: {
                total_payslips: 0,
                gross_total: 0,
                deductions_total: 0,
                net_total: 0,
                currency: "₹",
                paid_count: 0,
                pending_count: 0,
            },
            daily_attendance: {
                date: "—",
                total: 0,
                present: 0,
                absent: 0,
                on_leave: 0,
                still_checked_in: 0,
                checked_out: 0,   // ← NEW
                missed_out: 0,
                live_records: [],
            },
            leaves_for_approval: {
                total_pending: 0,
                records: [],
                by_type: [],
            },
            loan_summary: {
                available: false,
                total_to_recover: 0,
                total_recovered: 0,
                total_given: 0,  // ← add this
                active_loans: 0,
                records: [],
                currency: '₹',
            },
            payslip_summary: {
                total: 0,
                by_state: [],
                recent: [],
                currency: "₹",
                month: "—",
            },
            new_joinees: {
                count: 0,
                records: [],
                month: "—",
            },
            monthly_attendance_trend: [],
            salary_report: { total_ctc: 0, total_gross: 0, currency: '₹' },
            german_salary_report: { total_ctc: 0, total_gross: 0, currency: '₹' },
            extra: {
                timesheets: 0,
                contracts: 0,
                broad_factor: 0,
                leave_today: 0,
                leave_month: 0,
                leave_allocations: 0,
                job_applications: 0,
                dept_total: 0,
                dept_distribution: [],
                monthly_leave_analysis: [],
                my_leave_analysis: [],
                join_resign: [],
                attrition: [],
                birthdays: [],
                events: [],
                announcements: [],
            },
            salary_report: {
                total_ctc: 0,
                total_gross: 0,
                total_inhand: 0,
                total_net: 0,
                total_pf: 0,
                currency: '₹'
            },
        };
    }

    // ── Fetch all dashboard data from Python model ────────────────────────
    async loadData() {
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "hr.payroll.custom.dashboard",
                "get_dashboard_data",
                [],
                { date_from: this.state.dateFrom, date_to: this.state.dateTo }
            );
            const empty = this._emptyData();
            const merged = Object.assign({}, empty, result);
            // Deep merge extra so missing keys fall back to empty defaults
            merged.extra = Object.assign({}, empty.extra, result.extra || {});
            // Ensure all array fields in extra are never undefined
            const arrayFields = [
                'dept_distribution','monthly_leave_analysis','my_leave_analysis',
                'join_resign','attrition','birthdays','events','announcements'
            ];
            for (const f of arrayFields) {
                if (!Array.isArray(merged.extra[f])) merged.extra[f] = [];
            }
            // Ensure salary_report always has all fields
            merged.salary_report = Object.assign(
                { total_ctc: 0, total_gross: 0, total_inhand: 0, total_net: 0, total_pf: 0, currency: '₹' },
                merged.salary_report || {}
            );
            merged.german_salary_report = Object.assign(
                { total_ctc: 0, total_gross: 0, currency: '₹' },
                merged.german_salary_report || {}
            );
            // Ensure all top-level objects exist before accessing their sub-fields
            if (!merged.daily_attendance || typeof merged.daily_attendance !== 'object') merged.daily_attendance = empty.daily_attendance;
            if (!Array.isArray(merged.daily_attendance.live_records)) merged.daily_attendance.live_records = [];
            if (!merged.leaves_for_approval || typeof merged.leaves_for_approval !== 'object') merged.leaves_for_approval = empty.leaves_for_approval;
            if (!merged.payslip_summary || typeof merged.payslip_summary !== 'object') merged.payslip_summary = empty.payslip_summary;
            if (!merged.loan_summary || typeof merged.loan_summary !== 'object') merged.loan_summary = empty.loan_summary;
            if (!merged.attendance_salary || typeof merged.attendance_salary !== 'object') merged.attendance_salary = empty.attendance_salary;
            if (!merged.new_joinees || typeof merged.new_joinees !== 'object') merged.new_joinees = empty.new_joinees;
            // Ensure all top-level arrays are never undefined
            if (!Array.isArray(merged.monthly_attendance_trend)) merged.monthly_attendance_trend = [];
            if (!Array.isArray(merged.leaves_for_approval.records)) merged.leaves_for_approval.records = [];
            if (!Array.isArray(merged.leaves_for_approval.by_type)) merged.leaves_for_approval.by_type = [];
            if (!Array.isArray(merged.payslip_summary.by_state)) merged.payslip_summary.by_state = [];
            if (!Array.isArray(merged.payslip_summary.recent)) merged.payslip_summary.recent = [];
            if (!Array.isArray(merged.loan_summary.records)) merged.loan_summary.records = [];
            if (!Array.isArray(merged.attendance_salary.records)) merged.attendance_salary.records = [];
            if (!Array.isArray(merged.new_joinees.records)) merged.new_joinees.records = [];
            this.state.data = merged;
            setTimeout(() => this._renderCharts(), 50);
//            this.state.deptSlices = this._buildDeptSlices(merged.extra.dept_distribution);
        } catch (error) {
            this.notification.add(
                "Failed to load dashboard data. Please check your permissions.",
                { type: "danger", title: "Dashboard Error" }
            );
            console.error("HrPayrollDashboard error:", error);
        } finally {
            this.state.loading = false;
        }
    }


    formatAmount(value) {
        if (!value && value !== 0) return "0";
        return Number(value).toLocaleString("en-IN", {
            maximumFractionDigits: 0,
        });
    }


    computeAttPct(att) {
        if (!att || !att.total) return 0;
        return Math.round((att.present / att.total) * 100);
    }


    computeDonutPresent(att) {
        const C = 314;
        if (!att || !att.total) return `0 ${C}`;
        const pct = att.present / att.total;
        const len = Math.round(pct * C);
        return `${len} ${C - len}`;
    }

    computeDonutLeave(att) {
        const C = 314;
        if (!att || !att.total) return `0 ${C}`;
        const pct = att.on_leave / att.total;
        const len = Math.round(pct * C);
        return `${len} ${C - len}`;
    }

    computeDonutLeaveOffset(att) {
        const C = 314;
        if (!att || !att.total) return 0;
        const presentLen = Math.round((att.present / att.total) * C);
        // Offset rotates the leave arc to start after present arc
        // SVG starts at 3 o'clock; we want 12 o'clock start
        return C - presentLen + C / 4;
    }

    _renderCharts() {
        this._drawLeaveChart();
        this._drawJoinResignChart();
        this._drawAttritionChart();
    }

    _drawLineChart({ canvasId, tooltipId, labels, datasets, yLabel = '' }) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const tooltip = document.getElementById(tooltipId);
        const ctx = canvas.getContext('2d');
        const W = canvas.offsetWidth;
        const H = canvas.height;
        canvas.width = W;

        const PAD = { top: 20, right: 20, bottom: 36, left: 44 };
        const chartW = W - PAD.left - PAD.right;
        const chartH = H - PAD.top - PAD.bottom;
        const n = labels.length;
        if (!n) return;

        const allVals = datasets.flatMap(d => d.data);
        const maxVal = Math.max(...allVals, 1);
        const step = chartW / (n - 1 || 1);

        const xOf = i => PAD.left + i * step;
        const yOf = v => PAD.top + chartH - (v / maxVal) * chartH;

        // Grid lines
        ctx.clearRect(0, 0, W, H);
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        for (let g = 0; g <= 4; g++) {
            const y = PAD.top + (chartH / 4) * g;
            ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(W - PAD.right, y); ctx.stroke();
            ctx.fillStyle = '#9ca3af';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(Math.round(maxVal - (maxVal / 4) * g), PAD.left - 6, y + 4);
        }

        // X labels
        ctx.fillStyle = '#6b7280';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        labels.forEach((lbl, i) => ctx.fillText(lbl, xOf(i), H - 6));

        // Draw each dataset
        datasets.forEach(ds => {
            const pts = ds.data.map((v, i) => [xOf(i), yOf(v)]);

            // Filled area
            ctx.beginPath();
            ctx.moveTo(pts[0][0], pts[0][1]);
            pts.forEach(([x, y]) => ctx.lineTo(x, y));
            ctx.lineTo(pts[pts.length - 1][0], PAD.top + chartH);
            ctx.lineTo(pts[0][0], PAD.top + chartH);
            ctx.closePath();
            const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + chartH);
            grad.addColorStop(0, ds.color + '44');
            grad.addColorStop(1, ds.color + '00');
            ctx.fillStyle = grad;
            ctx.fill();

            // Line
            ctx.beginPath();
            ctx.moveTo(pts[0][0], pts[0][1]);
            pts.forEach(([x, y]) => ctx.lineTo(x, y));
            ctx.strokeStyle = ds.color;
            ctx.lineWidth = 2.5;
            ctx.lineJoin = 'round';
            ctx.stroke();

            // Dots
            pts.forEach(([x, y]) => {
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fillStyle = '#fff';
                ctx.fill();
                ctx.strokeStyle = ds.color;
                ctx.lineWidth = 2;
                ctx.stroke();
            });
        });

        // Hover
        canvas.onmousemove = (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = (e.clientX - rect.left) * (W / rect.width);
            let closest = 0, minDist = Infinity;
            labels.forEach((_, i) => {
                const d = Math.abs(xOf(i) - mx);
                if (d < minDist) { minDist = d; closest = i; }
            });
            if (minDist > step * 0.6) { tooltip.classList.remove('visible'); return; }

            let html = `<strong>${labels[closest]}</strong><br>`;
            datasets.forEach(ds => {
                html += `<span style="color:${ds.color}">●</span> ${ds.label}: <strong>${ds.data[closest]}</strong><br>`;
            });
            tooltip.innerHTML = html;
            tooltip.classList.add('visible');

            const tx = xOf(closest) * (rect.width / W);
            const ty = yOf(Math.max(...datasets.map(d => d.data[closest]))) * (rect.height / H);
            tooltip.style.left = (tx + 12) + 'px';
            tooltip.style.top = (ty - 10) + 'px';

            // Keep tooltip inside bounds
            const wrap = canvas.parentElement;
            const tRight = tx + 12 + tooltip.offsetWidth;
            if (tRight > wrap.offsetWidth) {
                tooltip.style.left = (tx - tooltip.offsetWidth - 12) + 'px';
            }
        };
        canvas.onmouseleave = () => tooltip.classList.remove('visible');
    }

    _drawBarChart({ canvasId, tooltipId, labels, data, color }) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const tooltip = document.getElementById(tooltipId);
        const ctx = canvas.getContext('2d');
        const W = canvas.offsetWidth;
        const H = canvas.height;
        canvas.width = W;

        const PAD = { top: 20, right: 20, bottom: 36, left: 44 };
        const chartW = W - PAD.left - PAD.right;
        const chartH = H - PAD.top - PAD.bottom;
        const n = labels.length;
        if (!n) return;

        const maxVal = Math.max(...data, 1);
        const barW = (chartW / n) * 0.6;
        const gap = chartW / n;

        ctx.clearRect(0, 0, W, H);

        // Grid
        ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
        for (let g = 0; g <= 4; g++) {
            const y = PAD.top + (chartH / 4) * g;
            ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(W - PAD.right, y); ctx.stroke();
            ctx.fillStyle = '#9ca3af'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
            ctx.fillText(Math.round(maxVal - (maxVal / 4) * g), PAD.left - 6, y + 4);
        }

        // Bars
        data.forEach((v, i) => {
            const x = PAD.left + i * gap + (gap - barW) / 2;
            const barH = (v / maxVal) * chartH;
            const y = PAD.top + chartH - barH;

            const grad = ctx.createLinearGradient(0, y, 0, y + barH);
            grad.addColorStop(0, color);
            grad.addColorStop(1, color + '88');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.roundRect(x, y, barW, barH, [4, 4, 0, 0]);
            ctx.fill();

            ctx.fillStyle = '#6b7280'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
            ctx.fillText(labels[i], PAD.left + i * gap + gap / 2, H - 6);
        });

        // Hover
        canvas.onmousemove = (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = (e.clientX - rect.left) * (W / rect.width);
            let hit = -1;
            data.forEach((_, i) => {
                const cx = PAD.left + i * gap + gap / 2;
                if (Math.abs(mx - cx) < gap / 2) hit = i;
            });
            if (hit < 0) { tooltip.classList.remove('visible'); return; }
            tooltip.innerHTML = `<strong>${labels[hit]}</strong><br><span style="color:${color}">●</span> Leaves: <strong>${data[hit]}</strong>`;
            tooltip.classList.add('visible');
            const tx = (PAD.left + hit * gap + gap / 2) * (rect.width / W);
            const barH = (data[hit] / maxVal) * chartH;
            const ty = (PAD.top + chartH - barH) * (rect.height / H);
            tooltip.style.left = (tx + 12) + 'px';
            tooltip.style.top = (ty - 10) + 'px';
        };
        canvas.onmouseleave = () => tooltip.classList.remove('visible');
    }

    _drawLeaveChart() {
        const d = this.state.data.extra.monthly_leave_analysis || [];
        this._drawBarChart({
            canvasId: 'leaveChart',
            tooltipId: 'leaveTooltip',
            labels: d.map(x => x.month),
            data: d.map(x => x.total),
            color: '#6366f1',
        });
    }

    _drawJoinResignChart() {
        const d = this.state.data.extra.join_resign || [];
        this._drawLineChart({
            canvasId: 'joinResignChart',
            tooltipId: 'joinResignTooltip',
            labels: d.map(x => x.month),
            datasets: [
                { label: 'Join', data: d.map(x => x.joined), color: '#14b8a6' },
                { label: 'Resign', data: d.map(x => x.resigned), color: '#f97316' },
            ],
        });
    }

    _drawAttritionChart() {
        const d = this.state.data.extra.attrition || [];
        this._drawLineChart({
            canvasId: 'attritionChart',
            tooltipId: 'attritionTooltip',
            labels: d.map(x => x.month),
            datasets: [
                { label: 'Attrition', data: d.map(x => x.rate), color: '#14b8a6' },
            ],
        });
    }


    barHeight(count, total) {
        if (!total) return 2;
        return Math.max(4, Math.round((count / total) * 60));
    }
    // ── Chart helper methods ──────────────────────────────────────────────

    getDeptColor(index) {
        const colors = ['#14b8a6','#6366f1','#f59e0b','#22c55e','#ef4444','#8b5cf6','#06b6d4','#f97316'];
        return colors[index % colors.length];
    }

    joinPoints(data) {
        if (!data || !data.length) return '';
        const max = Math.max(...data.map(d => d.joined || 0), 1);
        const step = 400 / (data.length - 1 || 1);
        return data.map((d, i) => `${i * step},${100 - Math.round(((d.joined || 0) / max) * 85)}`).join(' ');
    }

    resignPoints(data) {
        if (!data || !data.length) return '';
        const max = Math.max(...data.map(d => d.resigned || 0), 1);
        const step = 400 / (data.length - 1 || 1);
        return data.map((d, i) => `${i * step},${100 - Math.round(((d.resigned || 0) / max) * 85)}`).join(' ');
    }
    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
    }

    onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
    }

    applyDateFilter() {
        this.loadData();
    }

    attritionPoints(data) {
        if (!data || !data.length) return '';
        const max = Math.max(...data.map(d => d.rate || 0), 1);
        const step = 400 / (data.length - 1 || 1);
        return data.map((d, i) => `${i * step},${100 - Math.round(((d.rate || 0) / max) * 85)}`).join(' ');
    }

    attritionCy(rate) {
        return 100 - Math.min((rate || 0) / 10 * 90, 90);
    }

    mlaBarHeight(total) {
        if (!total) return 2;
        return Math.max(4, Math.round((total / 30) * 80));
    }

    attritionCx(index, total) {
        const step = 400 / (total - 1 || 1);
        return index * step;
    }
    viewAll(modelOrAction, viewType = 'list', domain = []) {
        const builtinRoutes = {
            'payslips':      { type: 'ir.actions.act_window', name: 'Payslips',      res_model: 'hr.payslip',            views: [[false,'list'],[false,'form']], domain },
            'contracts':     { type: 'ir.actions.act_window', name: 'Contracts',     res_model: 'hr.contract',           views: [[false,'list'],[false,'form']], domain },
            'employees':     { type: 'ir.actions.act_window', name: 'Employees',     res_model: 'hr.employee',           views: [[false,'list'],[false,'form']], domain },
            'departments':   { type: 'ir.actions.act_window', name: 'Departments',   res_model: 'hr.department',         views: [[false,'list'],[false,'form']], domain },
            'leaves':        { type: 'ir.actions.act_window', name: 'Time Off',      res_model: 'hr.leave',              views: [[false,'list'],[false,'form']], domain },
            'attendance':    { type: 'ir.actions.act_window', name: 'Attendance',    res_model: 'hr.attendance',         views: [[false,'list'],[false,'form']], domain },
            'loans':         { type: 'ir.actions.act_window', name: 'Salary Attachments', res_model: 'hr.salary.attachment', views: [[false,'list'],[false,'form']], domain },
        };
        this.action.doAction(builtinRoutes[modelOrAction]);
    }

    doCheckout() {
        this.notification.add("Check-out recorded.", { type: "success" });
    }
}

registry.category("actions").add("hr_payroll_custom_dashboard", HrPayrollDashboard);