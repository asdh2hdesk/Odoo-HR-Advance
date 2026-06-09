/**
 * generate_profile.js
 * Generates German Green Steel and Power Limited Employee Profile DOCX.
 * Usage: node generate_profile.js <data.json> <output.docx>
 */

'use strict';

const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    AlignmentType, WidthType, BorderStyle, ShadingType, VerticalAlign,
    HeadingLevel, PageOrientation, Header, ImageRun,
} = require('docx');
const fs = require('fs');

const args = process.argv.slice(2);
if (args.length < 2) {
    console.error('Usage: node generate_profile.js <data.json> <output.docx>');
    process.exit(1);
}

const data = JSON.parse(fs.readFileSync(args[0], 'utf8'));
const outPath = args[1];

// ─── Colour palette ────────────────────────────────────────────────────────
const HEADER_FILL  = 'F5CBA7';   // salmon/peach (table header rows)
const BORDER_COLOR = 'B0B0B0';
const BLACK        = '000000';
const WHITE        = 'FFFFFF';

// ─── Common border set ─────────────────────────────────────────────────────
function bdr(color = BORDER_COLOR) {
    const s = { style: BorderStyle.SINGLE, size: 6, color };
    return { top: s, bottom: s, left: s, right: s };
}

function noBorder() {
    const s = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
    return { top: s, bottom: s, left: s, right: s };
}

// ─── Cell helpers ──────────────────────────────────────────────────────────
function cell(text, opts = {}) {
    const {
        bold = false,
        size = 16,          // half-points (16 = 8pt, 18 = 9pt, 20 = 10pt)
        fill = null,
        width = null,
        span = 1,
        align = AlignmentType.LEFT,
        vAlign = VerticalAlign.CENTER,
        italic = false,
        borders = bdr(),
        color = BLACK,
    } = opts;

    const cellOpts = {
        borders,
        verticalAlign: vAlign,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [
            new Paragraph({
                alignment: align,
                spacing: { before: 0, after: 0 },
                children: [
                    new TextRun({
                        text: String(text ?? '#N/A'),
                        bold,
                        size,
                        font: 'Arial',
                        color,
                        italics: italic,
                    }),
                ],
            }),
        ],
    };

    if (fill) {
        cellOpts.shading = { fill, type: ShadingType.CLEAR, color: 'auto' };
    }
    if (width) {
        cellOpts.width = { size: width, type: WidthType.DXA };
    }
    if (span > 1) {
        cellOpts.columnSpan = span;
    }

    return new TableCell(cellOpts);
}

// Header cell (salmon background, bold, centred)
function hCell(text, width = null, span = 1) {
    return cell(text, { bold: true, size: 16, fill: HEADER_FILL, width, span, align: AlignmentType.CENTER });
}

// SR NO cell
function srCell(num, width = 700) {
    return cell(String(num), { align: AlignmentType.CENTER, width, size: 16 });
}

// ─── Section heading row (full-width merged, centred, peach) ───────────────
function sectionHeadingRow(title, totalWidth, colCount) {
    return new TableRow({
        children: [
            new TableCell({
                columnSpan: colCount,
                width: { size: totalWidth, type: WidthType.DXA },
                shading: { fill: HEADER_FILL, type: ShadingType.CLEAR, color: 'auto' },
                borders: bdr(),
                margins: { top: 80, bottom: 80, left: 100, right: 100 },
                verticalAlign: VerticalAlign.CENTER,
                children: [
                    new Paragraph({
                        alignment: AlignmentType.CENTER,
                        spacing: { before: 0, after: 0 },
                        children: [
                            new TextRun({
                                text: title,
                                bold: true,
                                size: 18,
                                font: 'Arial',
                                underline: {},
                            }),
                        ],
                    }),
                ],
            }),
        ],
    });
}

// ─── Spacing paragraph ─────────────────────────────────────────────────────
function spacer(pts = 40) {
    return new Paragraph({ spacing: { before: 0, after: pts }, children: [] });
}

// ─── Page setup ────────────────────────────────────────────────────────────
// A4: 11906 × 16838 DXA.  Margins 720 (0.5") each side → content = 10466
const PAGE_W   = 11906;
const MARGIN   = 720;
const CONTENT  = PAGE_W - MARGIN * 2; // 10466

// ─── Build document ────────────────────────────────────────────────────────

// ── TOP INFO TABLE (Employee code / Date / Dept / Post / Blood + Photo box) ─
const topInfoTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: [2000, 3200, 3266, 2000],
    rows: [
        // Row: Employee Code
        new TableRow({
            children: [
                cell('EMPLOYEE CODE :-', { bold: true, size: 16, width: 2000, borders: noBorder() }),
                cell(data.employee_code, { size: 16, width: 3200, borders: noBorder() }),
                // Photo box spans 2 rows × 2 cols — we simulate with rowSpan later;
                // for simplicity use a merged cell with "PASSPORT SIZE PHOTO"
                cell('PASSPORT SIZE\nPHOTO', {
                    width: 5266, span: 2,
                    align: AlignmentType.CENTER,
                    borders: bdr(),
                    size: 16,
                    bold: true,
                }),
            ],
        }),
        new TableRow({
            children: [
                cell('DATE :-', { bold: true, size: 16, width: 2000, borders: noBorder() }),
                cell(data.date, { size: 16, width: 3200, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
            ],
        }),
        new TableRow({
            children: [
                cell('DEPARTMENT:-', { bold: true, size: 16, width: 2000, borders: noBorder() }),
                cell(data.department, { size: 16, width: 3200, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
            ],
        }),
        new TableRow({
            children: [
                cell('EMPLOEE POST OF-', { bold: true, size: 16, width: 2000, borders: noBorder() }),
                cell(data.post, { size: 16, width: 3200, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
            ],
        }),
        new TableRow({
            children: [
                cell('BLOOD GROOP:-', { bold: true, size: 16, width: 2000, borders: noBorder() }),
                cell(data.blood_group, { size: 16, width: 3200, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
                cell('', { width: 2633, borders: noBorder() }),
            ],
        }),
    ],
});

// ── REV stamp paragraph ────────────────────────────────────────────────────
const revStamp = new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { before: 40, after: 40 },
    children: [
        new TextRun({ text: 'REV/00/ 16/05/2026', size: 14, font: 'Arial' }),
    ],
});

// ─── PERSONAL DETAILS TABLE ────────────────────────────────────────────────
// Columns: SR NO | PARTICULAR | DETAILS (left half) | SR NO | PARTICULAR | DETAILS (right half)
// Total width: CONTENT = 10466
// Col widths: 600 | 1900 | 2333 | 600 | 2000 | 3033  = 10466
const C = [600, 1900, 2333, 600, 2000, 3033];

function pdRow(srL, particL, detailL, srR, particR, detailR) {
    return new TableRow({
        children: [
            srCell(srL, C[0]),
            cell(particL, { size: 15, width: C[1] }),
            cell(detailL, { size: 15, width: C[2] }),
            srCell(srR, C[3]),
            cell(particR, { size: 15, width: C[4] }),
            cell(detailR, { size: 15, width: C[5] }),
        ],
    });
}

const personalTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: C,
    rows: [
        // Section heading spanning all 6 cols
        sectionHeadingRow('PERSONAL DETAILS', CONTENT, 6),
        // Header row
        new TableRow({
            children: [
                hCell('SR NO', C[0]),
                hCell('PARTICULAR', C[1]),
                hCell('DETAILS', C[2] + C[3] + C[4] + C[5], 4),
            ],
        }),
        // Data rows
        new TableRow({
            children: [
                srCell(1, C[0]),
                cell('NAME', { size: 15, width: C[1] }),
                cell(data.name, { size: 15, width: C[2] + C[3] + C[4] + C[5], span: 4 }),
            ],
        }),
        new TableRow({
            children: [
                srCell(2, C[0]),
                cell("FATHER'S/HUSBAND\nNAME", { size: 15, width: C[1] }),
                cell(data.father_name, { size: 15, width: C[2] + C[3] + C[4] + C[5], span: 4 }),
            ],
        }),
        new TableRow({
            children: [
                srCell(3, C[0]),
                cell("MOTHER'S NAME", { size: 15, width: C[1] }),
                cell(data.mother_name, { size: 15, width: C[2] + C[3] + C[4] + C[5], span: 4 }),
            ],
        }),
        new TableRow({
            children: [
                srCell(4, C[0]),
                cell('ADDRESS', { size: 15, width: C[1] }),
                cell(data.address, { size: 15, width: C[2] + C[3] + C[4] + C[5], span: 4 }),
            ],
        }),
        new TableRow({
            children: [
                srCell(5, C[0]),
                cell('CONTACT NO.', { size: 15, width: C[1] }),
                cell(data.contact, { size: 15, width: C[2] + C[3] + C[4] + C[5], span: 4 }),
            ],
        }),
        new TableRow({
            children: [
                srCell(6, C[0]),
                cell('E MAIL ID', { size: 15, width: C[1] }),
                cell(data.email, { size: 15, width: C[2] + C[3] + C[4] + C[5], span: 4 }),
            ],
        }),
        // Dual-column rows (7-18)
        pdRow(7,  'LANGAUGE KNOWN', data.language,        13, 'FOOD PREFRENCE',  data.food_preference),
        pdRow(8,  'BIRTH DATE',     data.birth_date,      14, 'AADHAAR NO.',     data.aadhaar),
        pdRow(9,  'GENDER',         data.gender,          15, 'PAN CARD NO.',    data.pan),
        pdRow(10, 'MARITAL STATUS', data.marital,         16, 'NATIONALITY',     data.nationality),
        pdRow(11, 'HEIGHT',         data.height,          17, 'WEIGHT',          data.weight),
        pdRow(12, 'BANK ACCOUNT NO', data.bank_account,   18, 'UAN.NO',          data.uan),
    ],
});

// ─── QUALIFICATION TABLE ───────────────────────────────────────────────────
// Cols: EXAM | YEAR OF PASSING | BOARD/UNI. | PERCENTAGE
const QC = [Math.floor(CONTENT / 4), Math.floor(CONTENT / 4), Math.floor(CONTENT / 4), CONTENT - 3 * Math.floor(CONTENT / 4)];

function qualRow(q) {
    return new TableRow({
        children: [
            cell(q.exam,       { size: 15, width: QC[0] }),
            cell(q.year,       { size: 15, width: QC[1], align: AlignmentType.CENTER }),
            cell(q.board,      { size: 15, width: QC[2] }),
            cell(q.percentage, { size: 15, width: QC[3], align: AlignmentType.CENTER }),
        ],
    });
}

const qualificationTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: QC,
    rows: [
        sectionHeadingRow('QUALIFICATION DETAILS', CONTENT, 4),
        new TableRow({
            children: [
                hCell('EXAM', QC[0]),
                hCell('YEAR OF PASSING', QC[1]),
                hCell('BOARD/UNI.', QC[2]),
                hCell('PERCENTAGE', QC[3]),
            ],
        }),
        ...data.qualifications.map(qualRow),
    ],
});

// ─── EXPERIENCE TABLE ──────────────────────────────────────────────────────
// SR NO | COMPANY NAME | DESIGNATION | TIME PERIOD | REASON FOR
const EC = [500, 3000, 2500, 2000, CONTENT - 500 - 3000 - 2500 - 2000];

function expRow(e, i) {
    return new TableRow({
        children: [
            srCell(i + 1, EC[0]),
            cell(e.company,     { size: 15, width: EC[1] }),
            cell(e.designation, { size: 15, width: EC[2] }),
            cell(e.period,      { size: 15, width: EC[3], align: AlignmentType.CENTER }),
            cell(e.reason,      { size: 15, width: EC[4], align: AlignmentType.CENTER }),
        ],
    });
}

const experienceTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: EC,
    rows: [
        sectionHeadingRow('EXPERIENCE DETAILS', CONTENT, 5),
        new TableRow({
            children: [
                hCell('SR NO', EC[0]),
                hCell('COMPANY NAME', EC[1]),
                hCell('DESIGNATION', EC[2]),
                hCell('TIME PERIOD', EC[3]),
                hCell('REASON FOR', EC[4]),
            ],
        }),
        ...data.experiences.map(expRow),
    ],
});

// ─── FAMILY CONTACT TABLE ──────────────────────────────────────────────────
const FC = [Math.floor(CONTENT / 4), Math.floor(CONTENT / 4), Math.floor(CONTENT / 4), CONTENT - 3 * Math.floor(CONTENT / 4)];

function contactRow(c) {
    return new TableRow({
        children: [
            cell(c.name,     { size: 15, width: FC[0] }),
            cell(c.contact,  { size: 15, width: FC[1], align: AlignmentType.CENTER }),
            cell(c.relation, { size: 15, width: FC[2], align: AlignmentType.CENTER }),
            cell(c.address,  { size: 15, width: FC[3] }),
        ],
    });
}

const familyTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: FC,
    rows: [
        sectionHeadingRow('FAMILY CONTACT DETAILS', CONTENT, 4),
        new TableRow({
            children: [
                hCell('NAME', FC[0]),
                hCell('CONTACT NO.', FC[1]),
                hCell('RELATION', FC[2]),
                hCell('ADDRESS', FC[3]),
            ],
        }),
        ...data.family_contacts.map(contactRow),
    ],
});

// ─── EMERGENCY CONTACT TABLE ───────────────────────────────────────────────
const emergencyTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: FC,
    rows: [
        sectionHeadingRow('EMERGENCY CONTACT DETAILS', CONTENT, 4),
        new TableRow({
            children: [
                hCell('NAME', FC[0]),
                hCell('CONTACT NO.', FC[1]),
                hCell('RELATION', FC[2]),
                hCell('ADDRESS', FC[3]),
            ],
        }),
        new TableRow({
            children: [
                cell(data.emergency.name,     { size: 15, width: FC[0] }),
                cell(data.emergency.contact,  { size: 15, width: FC[1] }),
                cell(data.emergency.relation, { size: 15, width: FC[2] }),
                cell(data.emergency.address,  { size: 15, width: FC[3] }),
            ],
        }),
    ],
});

// ─── SALARY + SKILL ROW ────────────────────────────────────────────────────
// LAST SALARY | value | EXPECTED SALARY | value
const SC = [Math.floor(CONTENT * 0.25), Math.floor(CONTENT * 0.25), Math.floor(CONTENT * 0.25), CONTENT - 3 * Math.floor(CONTENT * 0.25)];
const salaryTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: SC,
    rows: [
        new TableRow({
            children: [
                cell('LAST SALARY',     { bold: true, size: 16, width: SC[0], fill: HEADER_FILL }),
                cell(data.last_salary,  { size: 15, width: SC[1] }),
                cell('EXPECTED SALARY', { bold: true, size: 16, width: SC[2], fill: HEADER_FILL }),
                cell(data.expected_salary, { size: 15, width: SC[3] }),
            ],
        }),
        new TableRow({
            children: [
                cell('JOB SKILL', { bold: true, size: 16, width: SC[0], fill: HEADER_FILL }),
                cell(data.job_skill, { size: 15, width: SC[1] + SC[2] + SC[3], span: 3 }),
            ],
        }),
    ],
});

// ─── INTERVIEWER / SELECTION TABLE ─────────────────────────────────────────
// Two columns: label | value | (signature col spanning rows on right)
// We use a 3-col layout: label(3000) | value(5466) | signature(2000)
const IC = [3000, 5466, 2000];
const totalIC = IC.reduce((a, b) => a + b, 0); // should be CONTENT

function iRow(label, value, sigText = '') {
    const children = [
        cell(label, { bold: true, size: 15, width: IC[0], fill: HEADER_FILL }),
        cell(value,  { size: 15, width: IC[1] }),
    ];
    if (sigText !== null) {
        children.push(cell(sigText, { size: 15, width: IC[2], borders: bdr() }));
    }
    return new TableRow({ children });
}

const interviewTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: IC,
    rows: [
        // "SIGNATURE" label top-right
        new TableRow({
            children: [
                cell('', { width: IC[0] + IC[1], span: 2, borders: noBorder() }),
                cell('SIGNATURE', { bold: true, size: 16, width: IC[2], align: AlignmentType.RIGHT, borders: noBorder() }),
            ],
        }),
        iRow('INTERVIEWER NAME',  data.interviewer),
        iRow('SELECTED/REJECTED', data.selected_rejected),
        iRow('DEPARTMENT',        data.dept_interview),
        iRow('DATE OF JOINING',   data.date_joining),
        iRow('FINAL SALARY',      data.final_salary),
        iRow('SELECTION DATE',    data.selection_date),
        iRow('REFERENCE',         data.reference),
    ],
});

// ─── SIGNATURE FOOTER (Dept Head | GM | HR Manager) ───────────────────────
const sigW = Math.floor(CONTENT / 3);
const sigTable = new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: [sigW, sigW, CONTENT - 2 * sigW],
    rows: [
        new TableRow({
            children: [
                cell('DEPARTMENT HEAD', { bold: true, size: 18, width: sigW, align: AlignmentType.CENTER, borders: noBorder() }),
                cell('GENERAL MANAGER', { bold: true, size: 18, width: sigW, align: AlignmentType.CENTER, borders: noBorder() }),
                cell('H.R.MANAGER',     { bold: true, size: 18, width: CONTENT - 2 * sigW, align: AlignmentType.CENTER, borders: noBorder() }),
            ],
        }),
        new TableRow({
            children: [
                cell('SIGNATURE', { bold: true, size: 16, width: sigW, align: AlignmentType.CENTER, borders: noBorder() }),
                cell('SIGNATURE', { bold: true, size: 16, width: sigW, align: AlignmentType.CENTER, borders: noBorder() }),
                cell('SIGNATURE', { bold: true, size: 16, width: CONTENT - 2 * sigW, align: AlignmentType.CENTER, borders: noBorder() }),
            ],
        }),
    ],
});

// ─── Company title paragraph ───────────────────────────────────────────────
const companyTitle = new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 80 },
    children: [
        new TextRun({
            text: 'GERMAN GREEN STEEL AND POWER LIMITED',
            bold: true,
            size: 40,
            font: 'Arial Black',
            color: BLACK,
        }),
    ],
});

// ─── Assemble document ─────────────────────────────────────────────────────
const doc = new Document({
    sections: [{
        properties: {
            page: {
                size: { width: PAGE_W, height: 16838 },
                margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
            },
        },
        children: [
            companyTitle,
            revStamp,
            topInfoTable,
            spacer(60),
            personalTable,
            spacer(60),
            qualificationTable,
            spacer(60),
            experienceTable,
            spacer(60),
            familyTable,
            spacer(60),
            emergencyTable,
            spacer(60),
            salaryTable,
            spacer(80),
            interviewTable,
            spacer(200),
            sigTable,
        ],
    }],
});

Packer.toBuffer(doc).then((buffer) => {
    fs.writeFileSync(outPath, buffer);
    console.log('DOCX written to', outPath);
}).catch((err) => {
    console.error('Error generating DOCX:', err);
    process.exit(1);
});
