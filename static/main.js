/**
 * Employee Payroll and Performance Appraisal Management System
 * Interactive Client-Side Logic & Dynamic Previews
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            if (alert && alert.parentElement) {
                alert.style.opacity = '0';
                alert.style.transition = 'opacity 0.4s ease';
                setTimeout(function () {
                    if (alert && alert.parentElement) {
                        alert.remove();
                    }
                }, 400);
            }
        }, 5000);
    });

    // 2. Real-time Duplicate Employee ID check on Add Employee Form
    const empIdInput = document.getElementById('emp_id');
    const empIdFeedback = document.getElementById('empIdFeedback');
    if (empIdInput && empIdFeedback) {
        let checkTimeout;
        const checkEmpId = function () {
            clearTimeout(checkTimeout);
            const val = empIdInput.value.trim().toUpperCase();
            if (val.length < 2) {
                empIdFeedback.innerHTML = '';
                empIdInput.style.borderColor = '';
                return;
            }
            checkTimeout = setTimeout(function () {
                fetch(`/api/check-emp-id/${encodeURIComponent(val)}`)
                    .then(function (res) { return res.json(); })
                    .then(function (data) {
                        if (data.exists) {
                            empIdFeedback.innerHTML = `<span style="color: #ef4444; font-weight: 600;"><i class="fa-solid fa-circle-xmark"></i> Employee ID '${data.emp_id}' already exists! Please use a unique ID.</span>`;
                            empIdInput.style.borderColor = '#ef4444';
                        } else {
                            empIdFeedback.innerHTML = `<span style="color: #10b981; font-weight: 500;"><i class="fa-solid fa-circle-check"></i> Employee ID '${data.emp_id}' is available.</span>`;
                            empIdInput.style.borderColor = '#10b981';
                        }
                    })
                    .catch(function () {});
            }, 250);
        };

        empIdInput.addEventListener('input', checkEmpId);
        empIdInput.addEventListener('blur', checkEmpId);
    }

    // 3. Client-side live search for employee table
    const searchInput = document.getElementById('employeeSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            const tableRows = document.querySelectorAll('.data-table tbody tr');

            tableRows.forEach(function (row) {
                const text = row.innerText.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // 4. Dynamic Interactive Calculation for Performance Appraisal
    const prodInput = document.getElementById('productivity');
    const qualInput = document.getElementById('quality');
    const teamInput = document.getElementById('teamwork');
    const attInput = document.getElementById('attendance');

    const liveScoreEl = document.getElementById('liveScore');
    const liveRatingEl = document.getElementById('liveRating');

    function calculateLiveRating(score) {
        if (score >= 90.0) return { text: 'Excellent', class: 'badge-excellent' };
        if (score >= 75.0) return { text: 'Good', class: 'badge-good' };
        if (score >= 60.0) return { text: 'Satisfactory', class: 'badge-satisfactory' };
        if (score >= 50.0) return { text: 'Average', class: 'badge-average' };
        return { text: 'Needs Improvement', class: 'badge-needs-improvement' };
    }

    function updateLiveAppraisal() {
        if (!prodInput || !qualInput || !teamInput || !attInput) return;

        const pStr = prodInput.value.trim();
        const qStr = qualInput.value.trim();
        const tStr = teamInput.value.trim();
        const aStr = attInput.value.trim();

        if (pStr === '' || qStr === '' || tStr === '' || aStr === '') {
            if (liveScoreEl) liveScoreEl.innerText = '--.--';
            if (liveRatingEl) {
                liveRatingEl.innerText = 'Awaiting Inputs';
                liveRatingEl.className = 'badge';
                liveRatingEl.style.backgroundColor = '#e2e8f0';
                liveRatingEl.style.color = '#475569';
            }
            return;
        }

        const p = parseFloat(pStr);
        const q = parseFloat(qStr);
        const t = parseFloat(tStr);
        const a = parseFloat(aStr);

        // Validation for 0 - 100
        if (isNaN(p) || isNaN(q) || isNaN(t) || isNaN(a) ||
            p < 0 || p > 100 || q < 0 || q > 100 || t < 0 || t > 100 || a < 0 || a > 100) {
            if (liveScoreEl) liveScoreEl.innerText = 'Invalid';
            if (liveRatingEl) {
                liveRatingEl.innerText = 'Scores must be 0-100';
                liveRatingEl.className = 'badge badge-needs-improvement';
                liveRatingEl.style.backgroundColor = '';
                liveRatingEl.style.color = '';
            }
            return;
        }

        const overall = ((p + q + t + a) / 4.0).toFixed(2);
        const ratingInfo = calculateLiveRating(parseFloat(overall));

        if (liveScoreEl) liveScoreEl.innerText = overall;
        if (liveRatingEl) {
            liveRatingEl.innerText = ratingInfo.text;
            liveRatingEl.className = 'badge ' + ratingInfo.class;
            liveRatingEl.style.backgroundColor = '';
            liveRatingEl.style.color = '';
        }
    }

    if (prodInput && qualInput && teamInput && attInput) {
        [prodInput, qualInput, teamInput, attInput].forEach(function (input) {
            input.addEventListener('input', updateLiveAppraisal);
        });
        // Run immediately if inputs already contain values
        updateLiveAppraisal();
    }

    // 5. Interactive Live Preview for Payroll Selection
    const empSelect = document.getElementById('payrollEmpSelect');
    if (empSelect) {
        empSelect.addEventListener('change', function () {
            const empId = this.value;
            if (!empId) return;

            // Load selected employee's payroll details
            window.location.href = `/payroll?emp_id=${encodeURIComponent(empId)}`;
        });
    }

    // 6. Print Trigger helper
    const printBtn = document.getElementById('printPayslipBtn');
    if (printBtn) {
        printBtn.addEventListener('click', function () {
            window.print();
        });
    }
});
