# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
import pytz

from odoo.tests.common import TransactionCase
from odoo import fields


class TestFactoryAttendanceProcessing(TransactionCase):

    def setUp(self):
        super(TestFactoryAttendanceProcessing, self).setUp()
        self.company = self.env.company
        self.company.write({
            'factory_ot_start_after_standard': True,
            'factory_grace_time_minutes': 15,
            'factory_shortage_policy': 'lop',
            'factory_auto_generate_work_entries': False,
        })

        # Create standard 8h calendar (Mon-Fri)
        self.calendar = self.env['resource.calendar'].create({
            'name': 'Standard 8h Calendar (Mon-Fri)',
            'company_id': self.company.id,
            'hours_per_day': 8.0,
            'tz': 'UTC',
            'attendance_ids': [
                (0, 0, {'name': 'Mon Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Mon Afternoon', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tue Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tue Afternoon', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wed Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wed Afternoon', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thu Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thu Afternoon', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Fri Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Fri Afternoon', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
            ]
        })

        self.employee = self.env['hr.employee'].create({
            'name': 'Factory Worker Ramesh',
            'company_id': self.company.id,
            'resource_calendar_id': self.calendar.id,
            'tz': 'UTC',
        })

        self.contract = self.env['hr.contract'].create({
            'name': 'Ramesh Contract',
            'employee_id': self.employee.id,
            'resource_calendar_id': self.calendar.id,
            'company_id': self.company.id,
            'wage': 30000,
            'date_start': date(2026, 1, 1),
            'state': 'open',
            'use_factory_attendance': True,
        })

        self.service = self.env['attendance.processor.service']

    def test_01_interval_summation(self):
        """Test SUM(intervals) with meal break on Monday"""
        test_date = date(2026, 7, 6) # Monday
        # Punch 1: 08:00 - 12:00 (4 hours)
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 6, 8, 0, 0),
            'check_out': datetime(2026, 7, 6, 12, 0, 0),
        })
        # Punch 2: 13:00 - 18:00 (5 hours)
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 6, 13, 0, 0),
            'check_out': datetime(2026, 7, 6, 18, 0, 0),
        })

        summary = self.service._process_single_employee_date(self.employee, test_date)

        self.assertEqual(summary.worked_hours, 9.0, "Worked hours should sum intervals to 9.0 hours (not 10h from 08:00 to 18:00)")
        self.assertEqual(summary.expected_hours, 8.0)
        self.assertEqual(summary.regular_hours, 8.0)
        self.assertEqual(summary.ot_hours, 1.0)
        self.assertEqual(summary.day_type, 'working_day')

    def test_02_working_day_overtime(self):
        """Test normal working day with 11 hours worked"""
        test_date = date(2026, 7, 7) # Tuesday
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 7, 8, 0, 0),
            'check_out': datetime(2026, 7, 7, 19, 0, 0), # 11 hours
        })

        summary = self.service._process_single_employee_date(self.employee, test_date)

        self.assertEqual(summary.worked_hours, 11.0)
        self.assertEqual(summary.regular_hours, 8.0)
        self.assertEqual(summary.ot_hours, 3.0)
        self.assertEqual(summary.shortage_hours, 0.0)

    def test_03_weekly_off_worked(self):
        """Test Sunday (Weekly Off) worked 10 hours -> 100% OT"""
        test_date = date(2026, 7, 5) # Sunday (Off)
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 5, 8, 0, 0),
            'check_out': datetime(2026, 7, 5, 18, 0, 0), # 10 hours
        })

        summary = self.service._process_single_employee_date(self.employee, test_date)

        self.assertEqual(summary.day_type, 'weekoff')
        self.assertEqual(summary.worked_hours, 10.0)
        self.assertEqual(summary.regular_hours, 0.0, "Regular hours must be 0 on Weekly Off")
        self.assertEqual(summary.ot_hours, 10.0, "All worked hours on Weekly Off must classify as OT")

    def test_04_shortage_calculation(self):
        """Test 5 hours worked on 8 hour expected day -> 3h shortage"""
        test_date = date(2026, 7, 8) # Wednesday
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 8, 8, 0, 0),
            'check_out': datetime(2026, 7, 8, 13, 0, 0), # 5 hours
        })

        summary = self.service._process_single_employee_date(self.employee, test_date)

        self.assertEqual(summary.worked_hours, 5.0)
        self.assertEqual(summary.regular_hours, 5.0)
        self.assertEqual(summary.shortage_hours, 3.0)

    def test_05_work_entry_generation(self):
        """Test generating work entries from daily summary"""
        test_date = date(2026, 7, 9) # Thursday
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 9, 8, 0, 0),
            'check_out': datetime(2026, 7, 9, 18, 0, 0), # 10 hours (8h Reg + 2h OT)
        })

        summary = self.service._process_single_employee_date(self.employee, test_date)
        summary.action_lock_and_generate_work_entries()

        self.assertEqual(summary.state, 'locked')
        self.assertTrue(len(summary.work_entry_ids) >= 2, "Must generate regular and overtime work entries")
