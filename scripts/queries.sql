SELECT b.branch_name,
       COUNT(*) AS patrons,
       ROUND(AVG(p.total_checkouts), 1) AS avg_checkouts
FROM patrons p
JOIN library_codes lc ON p.home_library_code = lc.library_code
JOIN branches b ON lc.branch_id = b.branch_id
GROUP BY b.branch_name
ORDER BY patrons DESC;

SELECT a.age_range_label,
       COUNT(*) AS patrons,
       ROUND(AVG(p.total_checkouts), 1) AS avg_checkouts,
       ROUND(AVG(p.total_renewals), 1) AS avg_renewals
FROM patrons p
JOIN age_ranges a ON p.age_range_id = a.age_range_id
GROUP BY a.age_range_label, a.sort_order
ORDER BY a.sort_order;

SELECT pt.patron_type_name,
       COUNT(*) AS patrons,
       ROUND(AVG(p.total_checkouts), 1) AS avg_checkouts
FROM patrons p
JOIN patron_types pt ON p.patron_type_code = pt.patron_type_code
GROUP BY pt.patron_type_name
ORDER BY avg_checkouts DESC;

SELECT year_registered, COUNT(*) AS patrons
FROM patrons
GROUP BY year_registered
ORDER BY year_registered;

SELECT n.notification_name,
       COUNT(*) AS patrons,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM patrons), 1) AS percent
FROM patrons p
JOIN notification_preferences n ON p.notification_code = n.notification_code
GROUP BY n.notification_name
ORDER BY patrons DESC;

SELECT within_sf_county,
       COUNT(*) AS patrons,
       ROUND(AVG(total_checkouts), 1) AS avg_checkouts
FROM patrons
GROUP BY within_sf_county;

SELECT COUNT(*) AS never_active,
       SUM(total_checkouts > 0) AS have_checkouts_anyway
FROM patrons
WHERE active_year IS NULL;

SELECT p.patron_id, pt.patron_type_name, b.branch_name,
       p.total_checkouts, p.year_registered
FROM patrons p
JOIN patron_types pt ON p.patron_type_code = pt.patron_type_code
JOIN library_codes lc ON p.home_library_code = lc.library_code
JOIN branches b ON lc.branch_id = b.branch_id
ORDER BY p.total_checkouts DESC
LIMIT 10;