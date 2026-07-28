/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AttendanceFlowDashboard extends Component {
    static template = "hr_factory_attendance_processing.AttendanceFlowDashboard";

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        
        this.state = useState({
            activeStep: 1,
            // Calculator simulator state
            simDayType: 'working_day',
            simExpectedHours: 8.0,
            simWorkedHours: 11.0,
            calcRegular: 8.0,
            calcOT: 3.0,
            calcShortage: 0.0,
        });

        this.calculateSimulation();
    }

    setStep(stepNumber) {
        this.state.activeStep = stepNumber;
    }

    onSimParamChange(ev, param) {
        const value = ev.target.value;
        if (param === 'simDayType') {
            this.state.simDayType = value;
        } else if (param === 'simExpectedHours') {
            this.state.simExpectedHours = parseFloat(value) || 0.0;
        } else if (param === 'simWorkedHours') {
            this.state.simWorkedHours = parseFloat(value) || 0.0;
        }
        this.calculateSimulation();
    }

    calculateSimulation() {
        const worked = this.state.simWorkedHours;
        const expected = this.state.simExpectedHours;
        const dayType = this.state.simDayType;

        if (dayType === 'weekoff' || dayType === 'public_holiday') {
            this.state.calcRegular = 0.0;
            this.state.calcOT = worked;
            this.state.calcShortage = 0.0;
        } else if (dayType === 'leave') {
            this.state.calcRegular = 0.0;
            this.state.calcOT = 0.0;
            this.state.calcShortage = 0.0;
        } else {
            if (worked === 0.0) {
                this.state.calcRegular = 0.0;
                this.state.calcOT = 0.0;
                this.state.calcShortage = expected;
            } else {
                this.state.calcRegular = Math.min(worked, expected);
                this.state.calcOT = Math.max(0.0, worked - expected);
                this.state.calcShortage = Math.max(0.0, expected - worked);
            }
        }
    }

    openWizard() {
        this.action.doAction("hr_factory_attendance_processing.attendance_processor_wizard_action");
    }

    openDailySummaries() {
        this.action.doAction("hr_factory_attendance_processing.attendance_daily_summary_action");
    }

    openSettings() {
        this.action.doAction("hr_attendance.action_hr_attendance_settings");
    }
}

registry.category("actions").add("hr_factory_attendance_flow_guide", AttendanceFlowDashboard);
