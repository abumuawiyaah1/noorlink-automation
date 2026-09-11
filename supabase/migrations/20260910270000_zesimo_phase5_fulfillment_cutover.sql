-- Zesimo Phase 5: ME silent cutover + tourist singles + ladder fills + strong adds.
-- Source: app/services/zesimo_sku_map.py (fulfillment_rows), 142 SKUs.

insert into public.plan_fulfillment_map (
  catalog_key, country_code, country_slug, data_gb, validity_days,
  provider, provider_sku, provider_slug, wholesale_cents, notes, is_active, admin_approved
)
values
  ('me-1gb-7', null, 'regional-middle-east', 1.0, 7, 'zesimo', '1083', 'zesimo-me-1gb-7d', 233, 'Zesimo phase 5: MIDDLE EAST 1GB 7 Days', true, true)
  ('sa-unlimited-3gb-7d', 'SA', 'saudi-arabia', 3.0, 7, 'zesimo', '10903', 'zesimo-sa-unlimited-7d', 2142, 'Zesimo phase 1: Saudi Arabia Unlimited 7 Days', true, true)
  ('sa-unlimited-3gb-10d', 'SA', 'saudi-arabia', 3.0, 10, 'zesimo', '10905', 'zesimo-sa-unlimited-10d', 2786, 'Zesimo phase 1: Saudi Arabia Unlimited 10 Days', true, true)
  ('me-5gb-15', null, 'regional-middle-east', 5.0, 15, 'zesimo', '1085', 'zesimo-me-5gb-15d', 991, 'Zesimo phase 1: MIDDLE EAST 5GB 15 Days', true, true)
  ('me-10gb-30', null, 'regional-middle-east', 10.0, 30, 'zesimo', '1086', 'zesimo-me-10gb-30d', 1784, 'Zesimo phase 1: MIDDLE EAST 10GB 30 Days', true, true)
  ('eu-5gb-30', null, 'regional-europe', 5.0, 30, 'zesimo', '11707', 'zesimo-eu-5gb-30d', 602, 'Zesimo phase 2: Europe 5GB 30 Days', true, true)
  ('eu-10gb-30', null, 'regional-europe', 10.0, 30, 'zesimo', '11709', 'zesimo-eu-10gb-30d', 966, 'Zesimo phase 2: Europe 10GB 30 Days', true, true)
  ('la-5gb-30', null, 'regional-south-america', 5.0, 30, 'zesimo', '12121', 'zesimo-la-5gb-30d', 1050, 'Zesimo phase 2: Latin America 5GB 30 Days', true, true)
  ('la-10gb-30', null, 'regional-south-america', 10.0, 30, 'zesimo', '12122', 'zesimo-la-10gb-30d', 1764, 'Zesimo phase 2: Latin America 10GB 30 Days', true, true)
  ('mx-5gb-30', 'MX', 'mexico', 5.0, 30, 'zesimo', '8186', 'zesimo-mx-5gb-30d', 812, 'Zesimo phase 2: Mexico 5GB 30 Days', true, true)
  ('mx-10gb-30', 'MX', 'mexico', 10.0, 30, 'zesimo', '8188', 'zesimo-mx-10gb-30d', 1400, 'Zesimo phase 2: Mexico 10GB 30 Days', true, true)
  ('us-5gb-30', 'US', 'united-states', 5.0, 30, 'zesimo', '3363', 'zesimo-us-5gb-30d', 463, 'Zesimo phase 2: United States 5GB 30 Days', true, true)
  ('us-10gb-30', 'US', 'united-states', 10.0, 30, 'zesimo', '7673', 'zesimo-us-10gb-30d', 809, 'Zesimo phase 2: United States 10GB 30 Days', true, true)
  ('na-10gb-30', null, 'regional-north-america', 10.0, 30, 'zesimo', '587', 'zesimo-na-10gb-30d', 1403, 'Zesimo phase 2: North America 10GB 30 Days', true, true)
  ('as-5gb-30', null, 'regional-asia-pacific', 5.0, 30, 'zesimo', '11733', 'zesimo-as-5gb-30d', 434, 'Zesimo phase 2: Asia 5GB 30 Days', true, true)
  ('as-10gb-30', null, 'regional-asia-pacific', 10.0, 30, 'zesimo', '11736', 'zesimo-as-10gb-30d', 714, 'Zesimo phase 2: Asia 10GB 30 Days', true, true)
  ('eu-20gb-30', null, 'regional-europe', 20.0, 30, 'zesimo', '11711', 'zesimo-eu-20gb-30d', 1526, 'Zesimo phase 3: Europe 20GB 30 Days', true, true)
  ('as-20gb-30', null, 'regional-asia-pacific', 20.0, 30, 'zesimo', '11738', 'zesimo-as-20gb-30d', 1092, 'Zesimo phase 3: Asia 20GB 30 Days', true, true)
  ('us-20gb-30', 'US', 'united-states', 20.0, 30, 'zesimo', '7677', 'zesimo-us-20gb-30d', 1450, 'Zesimo phase 3: United States 20GB 30 Days', true, true)
  ('la-20gb-30', null, 'regional-south-america', 20.0, 30, 'zesimo', '12123', 'zesimo-la-20gb-30d', 2814, 'Zesimo phase 3: Latin America 20GB 30 Days', true, true)
  ('mx-20gb-30', 'MX', 'mexico', 20.0, 30, 'zesimo', '8190', 'zesimo-mx-20gb-30d', 2226, 'Zesimo phase 3: Mexico 20GB 30 Days', true, true)
  ('eu-1gb-7', null, 'regional-europe', 1.0, 7, 'zesimo', '11701', 'zesimo-eu-1gb-7d', 252, 'Zesimo phase 3: Europe 1GB 7 Days', true, true)
  ('na-1gb-7', null, 'regional-north-america', 1.0, 7, 'zesimo', '580', 'zesimo-na-1gb-7d', 182, 'Zesimo phase 3: North America 1GB 7 Days', true, true)
  ('gulf-5gb-30', null, 'regional-gulf', 5.0, 30, 'zesimo', '2544', 'zesimo-gulf-5gb-30d', 1512, 'Zesimo phase 3: Gulf Region 5GB 30 Days', true, true)
  ('la-3gb-30', null, 'regional-south-america', 3.0, 30, 'zesimo', '12094', 'zesimo-la-3gb-30d', 700, 'Zesimo phase 3: Latin America 3GB 30 Days', true, true)
  ('gl-1gb-5', null, 'regional-global', 1.0, 5, 'zesimo', '11818', 'zesimo-global-1gb-5d', 350, 'Zesimo phase 4: Global 1GB 5 Days', true, true)
  ('gl-3gb-30', null, 'regional-global', 3.0, 30, 'zesimo', '11804', 'zesimo-global-3gb-30d', 938, 'Zesimo phase 4: Global 3GB 30 Days', true, true)
  ('gl-5gb-30', null, 'regional-global', 5.0, 30, 'zesimo', '11806', 'zesimo-global-5gb-30d', 1470, 'Zesimo phase 4: Global 5GB 30 Days', true, true)
  ('gl-10gb-30', null, 'regional-global', 10.0, 30, 'zesimo', '11808', 'zesimo-global-10gb-30d', 2520, 'Zesimo phase 4: Global 10GB 30 Days', true, true)
  ('na-3gb-30', null, 'regional-north-america', 3.0, 30, 'zesimo', '2290', 'zesimo-na-3gb-30d', 785, 'Zesimo phase 4: North America 3GB 30 Days', true, true)
  ('na-5gb-30', null, 'regional-north-america', 5.0, 30, 'zesimo', '7063', 'zesimo-na-5gb-30d', 1175, 'Zesimo phase 4: North America 5GB 30 Days', true, true)
  ('turkey-1gb-7', 'TR', 'turkey', 1.0, 7, 'zesimo', '1758', 'zesimo-turkey-1gb-7', 64, 'Zesimo phase 5: Turkey 1GB 7 Days', true, true)
  ('turkey-3gb-7', 'TR', 'turkey', 3.0, 7, 'zesimo', '537', 'zesimo-turkey-3gb-7', 220, 'Zesimo phase 5: Turkey 3GB 7 Days', true, true)
  ('turkey-5gb-15', 'TR', 'turkey', 5.0, 15, 'zesimo', '538', 'zesimo-turkey-5gb-15', 349, 'Zesimo phase 5: Turkey 5GB 15 Days', true, true)
  ('turkey-10gb-30', 'TR', 'turkey', 10.0, 30, 'zesimo', '1761', 'zesimo-turkey-10gb-30', 449, 'Zesimo phase 5: Turkey 10GB 30 Days', true, true)
  ('turkey-20gb-30', 'TR', 'turkey', 20.0, 30, 'zesimo', '8083', 'zesimo-turkey-20gb-30', 728, 'Zesimo phase 5: Turkey 20GB 30 Days', true, true)
  ('uae-1gb-7', 'AE', 'uae', 1.0, 7, 'zesimo', '2047', 'zesimo-uae-1gb-7', 245, 'Zesimo phase 5: United Arab Emirates 1GB 7 Days', true, true)
  ('uae-3gb-7', 'AE', 'uae', 3.0, 7, 'zesimo', '555', 'zesimo-uae-3gb-7', 902, 'Zesimo phase 5: United Arab Emirates 3GB 7 Days', true, true)
  ('uae-5gb-15', 'AE', 'uae', 5.0, 15, 'zesimo', '556', 'zesimo-uae-5gb-15', 1427, 'Zesimo phase 5: United Arab Emirates 5GB 15 Days', true, true)
  ('uae-10gb-30', 'AE', 'uae', 10.0, 30, 'zesimo', '8494', 'zesimo-uae-10gb-30', 1596, 'Zesimo phase 5: United Arab Emirates 10GB 30 Days', true, true)
  ('uae-20gb-30', 'AE', 'uae', 20.0, 30, 'zesimo', '8496', 'zesimo-uae-20gb-30', 2520, 'Zesimo phase 5: United Arab Emirates 20GB 30 Days', true, true)
  ('egypt-1gb-7', 'EG', 'egypt', 1.0, 7, 'zesimo', '152', 'zesimo-egypt-1gb-7', 130, 'Zesimo phase 5: Egypt 1GB 7 Days', true, true)
  ('egypt-3gb-7', 'EG', 'egypt', 3.0, 7, 'zesimo', '153', 'zesimo-egypt-3gb-7', 352, 'Zesimo phase 5: Egypt 3GB 7 Days', true, true)
  ('egypt-5gb-15', 'EG', 'egypt', 5.0, 15, 'zesimo', '154', 'zesimo-egypt-5gb-15', 557, 'Zesimo phase 5: Egypt 5GB 15 Days', true, true)
  ('egypt-10gb-30', 'EG', 'egypt', 10.0, 30, 'zesimo', '155', 'zesimo-egypt-10gb-30', 1003, 'Zesimo phase 5: Egypt 10GB 30 Days', true, true)
  ('egypt-20gb-30', 'EG', 'egypt', 20.0, 30, 'zesimo', '156', 'zesimo-egypt-20gb-30', 1769, 'Zesimo phase 5: Egypt 20GB 30 Days', true, true)
  ('qatar-1gb-7', 'QA', 'qatar', 1.0, 7, 'zesimo', '446', 'zesimo-qatar-1gb-7', 155, 'Zesimo phase 5: Qatar 1GB 7 Days', true, true)
  ('qatar-3gb-7', 'QA', 'qatar', 3.0, 7, 'zesimo', '447', 'zesimo-qatar-3gb-7', 419, 'Zesimo phase 5: Qatar 3GB 7 Days', true, true)
  ('qatar-5gb-15', 'QA', 'qatar', 5.0, 15, 'zesimo', '448', 'zesimo-qatar-5gb-15', 661, 'Zesimo phase 5: Qatar 5GB 15 Days', true, true)
  ('qatar-10gb-30', 'QA', 'qatar', 10.0, 30, 'zesimo', '10799', 'zesimo-qatar-10gb-30', 1022, 'Zesimo phase 5: Qatar 10GB 30 Days', true, true)
  ('qatar-20gb-30', 'QA', 'qatar', 20.0, 30, 'zesimo', '450', 'zesimo-qatar-20gb-30', 2101, 'Zesimo phase 5: Qatar 20GB 30 Days', true, true)
  ('kuwait-1gb-7', 'KW', 'kuwait', 1.0, 7, 'zesimo', '296', 'zesimo-kuwait-1gb-7', 135, 'Zesimo phase 5: Kuwait 1GB 7 Days', true, true)
  ('kuwait-3gb-7', 'KW', 'kuwait', 3.0, 7, 'zesimo', '297', 'zesimo-kuwait-3gb-7', 365, 'Zesimo phase 5: Kuwait 3GB 7 Days', true, true)
  ('kuwait-5gb-15', 'KW', 'kuwait', 5.0, 15, 'zesimo', '298', 'zesimo-kuwait-5gb-15', 578, 'Zesimo phase 5: Kuwait 5GB 15 Days', true, true)
  ('kuwait-10gb-30', 'KW', 'kuwait', 10.0, 30, 'zesimo', '299', 'zesimo-kuwait-10gb-30', 1041, 'Zesimo phase 5: Kuwait 10GB 30 Days', true, true)
  ('kuwait-20gb-30', 'KW', 'kuwait', 20.0, 30, 'zesimo', '300', 'zesimo-kuwait-20gb-30', 1836, 'Zesimo phase 5: Kuwait 20GB 30 Days', true, true)
  ('bahrain-1gb-7', 'BH', 'bahrain', 1.0, 7, 'zesimo', '56', 'zesimo-bahrain-1gb-7', 179, 'Zesimo phase 5: Bahrain 1GB 7 Days', true, true)
  ('bahrain-3gb-7', 'BH', 'bahrain', 3.0, 7, 'zesimo', '57', 'zesimo-bahrain-3gb-7', 484, 'Zesimo phase 5: Bahrain 3GB 7 Days', true, true)
  ('bahrain-5gb-15', 'BH', 'bahrain', 5.0, 15, 'zesimo', '58', 'zesimo-bahrain-5gb-15', 765, 'Zesimo phase 5: Bahrain 5GB 15 Days', true, true)
  ('bahrain-10gb-30', 'BH', 'bahrain', 10.0, 30, 'zesimo', '59', 'zesimo-bahrain-10gb-30', 1378, 'Zesimo phase 5: Bahrain 10GB 30 Days', true, true)
  ('bahrain-20gb-30', 'BH', 'bahrain', 20.0, 30, 'zesimo', '60', 'zesimo-bahrain-20gb-30', 2432, 'Zesimo phase 5: Bahrain 20GB 30 Days', true, true)
  ('oman-1gb-7', 'OM', 'oman', 1.0, 7, 'zesimo', '750', 'zesimo-oman-1gb-7', 182, 'Zesimo phase 5: Oman 1GB 7 Days', true, true)
  ('oman-3gb-7', 'OM', 'oman', 3.0, 7, 'zesimo', '751', 'zesimo-oman-3gb-7', 492, 'Zesimo phase 5: Oman 3GB 7 Days', true, true)
  ('oman-5gb-15', 'OM', 'oman', 5.0, 15, 'zesimo', '752', 'zesimo-oman-5gb-15', 780, 'Zesimo phase 5: Oman 5GB 15 Days', true, true)
  ('oman-10gb-30', 'OM', 'oman', 10.0, 30, 'zesimo', '753', 'zesimo-oman-10gb-30', 1404, 'Zesimo phase 5: Oman 10GB 30 Days', true, true)
  ('oman-20gb-30', 'OM', 'oman', 20.0, 30, 'zesimo', '754', 'zesimo-oman-20gb-30', 2476, 'Zesimo phase 5: Oman 20GB 30 Days', true, true)
  ('morocco-1gb-7', 'MA', 'morocco', 1.0, 7, 'zesimo', '1887', 'zesimo-morocco-1gb-7', 167, 'Zesimo phase 5: Morocco 1GB 7 Days', true, true)
  ('morocco-3gb-7', 'MA', 'morocco', 3.0, 7, 'zesimo', '357', 'zesimo-morocco-3gb-7', 787, 'Zesimo phase 5: Morocco 3GB 7 Days', true, true)
  ('morocco-5gb-15', 'MA', 'morocco', 5.0, 15, 'zesimo', '358', 'zesimo-morocco-5gb-15', 1246, 'Zesimo phase 5: Morocco 5GB 15 Days', true, true)
  ('morocco-10gb-30', 'MA', 'morocco', 10.0, 30, 'zesimo', '2563', 'zesimo-morocco-10gb-30', 1219, 'Zesimo phase 5: Morocco 10GB 30 Days', true, true)
  ('morocco-20gb-30', 'MA', 'morocco', 20.0, 30, 'zesimo', '2201', 'zesimo-morocco-20gb-30', 2164, 'Zesimo phase 5: Morocco 20GB 30 Days', true, true)
  ('jordan-1gb-7', 'JO', 'jordan', 1.0, 7, 'zesimo', '1787', 'zesimo-jordan-1gb-7', 260, 'Zesimo phase 5: Jordan 1GB 7 Days', true, true)
  ('jordan-3gb-7', 'JO', 'jordan', 3.0, 7, 'zesimo', '273', 'zesimo-jordan-3gb-7', 1182, 'Zesimo phase 5: Jordan 3GB 7 Days', true, true)
  ('jordan-5gb-15', 'JO', 'jordan', 5.0, 15, 'zesimo', '274', 'zesimo-jordan-5gb-15', 1873, 'Zesimo phase 5: Jordan 5GB 15 Days', true, true)
  ('jordan-10gb-30', 'JO', 'jordan', 10.0, 30, 'zesimo', '6567', 'zesimo-jordan-10gb-30', 1845, 'Zesimo phase 5: Jordan 10GB 30 Days', true, true)
  ('jordan-20gb-30', 'JO', 'jordan', 20.0, 30, 'zesimo', '6570', 'zesimo-jordan-20gb-30', 3382, 'Zesimo phase 5: Jordan 20GB 30 Days', true, true)
  ('uk-1gb-7', 'GB', 'uk', 1.0, 7, 'zesimo', '1725', 'zesimo-uk-1gb-7', 80, 'Zesimo phase 5: United Kingdom 1GB 7 Days', true, true)
  ('uk-5gb-30', 'GB', 'uk', 5.0, 30, 'zesimo', '1611', 'zesimo-uk-5gb-30', 333, 'Zesimo phase 5: United Kingdom 5GB 30 Days', true, true)
  ('uk-10gb-30', 'GB', 'uk', 10.0, 30, 'zesimo', '1727', 'zesimo-uk-10gb-30', 599, 'Zesimo phase 5: United Kingdom 10GB 30 Days', true, true)
  ('uk-20gb-30', 'GB', 'uk', 20.0, 30, 'zesimo', '11554', 'zesimo-uk-20gb-30', 1008, 'Zesimo phase 5: United Kingdom 20GB 30 Days', true, true)
  ('spain-1gb-7', 'ES', 'spain', 1.0, 7, 'zesimo', '1717', 'zesimo-spain-1gb-7', 80, 'Zesimo phase 5: Spain 1GB 7 Days', true, true)
  ('spain-5gb-30', 'ES', 'spain', 5.0, 30, 'zesimo', '11563', 'zesimo-spain-5gb-30', 308, 'Zesimo phase 5: Spain 5GB 30 Days', true, true)
  ('spain-10gb-30', 'ES', 'spain', 10.0, 30, 'zesimo', '11565', 'zesimo-spain-10gb-30', 462, 'Zesimo phase 5: Spain 10GB 30 Days', true, true)
  ('spain-20gb-30', 'ES', 'spain', 20.0, 30, 'zesimo', '11567', 'zesimo-spain-20gb-30', 686, 'Zesimo phase 5: Spain 20GB 30 Days', true, true)
  ('italy-1gb-7', 'IT', 'italy', 1.0, 7, 'zesimo', '1699', 'zesimo-italy-1gb-7', 80, 'Zesimo phase 5: Italy 1GB 7 Days', true, true)
  ('italy-5gb-30', 'IT', 'italy', 5.0, 30, 'zesimo', '8055', 'zesimo-italy-5gb-30', 322, 'Zesimo phase 5: Italy 5GB 30 Days', true, true)
  ('italy-10gb-30', 'IT', 'italy', 10.0, 30, 'zesimo', '1701', 'zesimo-italy-10gb-30', 599, 'Zesimo phase 5: Italy 10GB 30 Days', true, true)
  ('italy-20gb-30', 'IT', 'italy', 20.0, 30, 'zesimo', '8059', 'zesimo-italy-20gb-30', 980, 'Zesimo phase 5: Italy 20GB 30 Days', true, true)
  ('germany-1gb-7', 'DE', 'germany', 1.0, 7, 'zesimo', '1644', 'zesimo-germany-1gb-7', 80, 'Zesimo phase 5: Germany 1GB 7 Days', true, true)
  ('germany-5gb-30', 'DE', 'germany', 5.0, 30, 'zesimo', '1593', 'zesimo-germany-5gb-30', 333, 'Zesimo phase 5: Germany 5GB 30 Days', true, true)
  ('germany-10gb-30', 'DE', 'germany', 10.0, 30, 'zesimo', '1646', 'zesimo-germany-10gb-30', 599, 'Zesimo phase 5: Germany 10GB 30 Days', true, true)
  ('germany-20gb-30', 'DE', 'germany', 20.0, 30, 'zesimo', '8179', 'zesimo-germany-20gb-30', 1092, 'Zesimo phase 5: Germany 20GB 30 Days', true, true)
  ('france-1gb-7', 'FR', 'france', 1.0, 7, 'zesimo', '182', 'zesimo-france-1gb-7', 90, 'Zesimo phase 5: France 1GB 7 Days', true, true)
  ('france-5gb-30', 'FR', 'france', 5.0, 30, 'zesimo', '1592', 'zesimo-france-5gb-30', 378, 'Zesimo phase 5: France 5GB 30 Days', true, true)
  ('france-10gb-30', 'FR', 'france', 10.0, 30, 'zesimo', '12193', 'zesimo-france-10gb-30', 616, 'Zesimo phase 5: France 10GB 30 Days', true, true)
  ('france-20gb-30', 'FR', 'france', 20.0, 30, 'zesimo', '12195', 'zesimo-france-20gb-30', 924, 'Zesimo phase 5: France 20GB 30 Days', true, true)
  ('japan-5gb-30', 'JP', 'japan', 5.0, 30, 'zesimo', '1779', 'zesimo-japan-5gb-30', 378, 'Zesimo phase 5: Japan 5GB 30 Days', true, true)
  ('japan-10gb-30', 'JP', 'japan', 10.0, 30, 'zesimo', '1780', 'zesimo-japan-10gb-30', 658, 'Zesimo phase 5: Japan 10GB 30 Days', true, true)
  ('japan-20gb-30', 'JP', 'japan', 20.0, 30, 'zesimo', '2145', 'zesimo-japan-20gb-30', 1148, 'Zesimo phase 5: Japan 20GB 30 Days', true, true)
  ('thailand-5gb-30', 'TH', 'thailand', 5.0, 30, 'zesimo', '1531', 'zesimo-thailand-5gb-30', 378, 'Zesimo phase 5: Thailand 5GB 30 Days', true, true)
  ('thailand-10gb-30', 'TH', 'thailand', 10.0, 30, 'zesimo', '1757', 'zesimo-thailand-10gb-30', 658, 'Zesimo phase 5: Thailand 10GB 30 Days', true, true)
  ('thailand-20gb-30', 'TH', 'thailand', 20.0, 30, 'zesimo', '8208', 'zesimo-thailand-20gb-30', 1050, 'Zesimo phase 5: Thailand 20GB 30 Days', true, true)
  ('indonesia-5gb-30', 'ID', 'indonesia', 5.0, 30, 'zesimo', '1772', 'zesimo-indonesia-5gb-30', 378, 'Zesimo phase 5: Indonesia 5GB 30 Days', true, true)
  ('indonesia-10gb-30', 'ID', 'indonesia', 10.0, 30, 'zesimo', '1773', 'zesimo-indonesia-10gb-30', 658, 'Zesimo phase 5: Indonesia 10GB 30 Days', true, true)
  ('indonesia-20gb-30', 'ID', 'indonesia', 20.0, 30, 'zesimo', '9685', 'zesimo-indonesia-20gb-30', 1050, 'Zesimo phase 5: Indonesia 20GB 30 Days', true, true)
  ('singapore-5gb-30', 'SG', 'singapore', 5.0, 30, 'zesimo', '1750', 'zesimo-singapore-5gb-30', 337, 'Zesimo phase 5: Singapore 5GB 30 Days', true, true)
  ('singapore-10gb-30', 'SG', 'singapore', 10.0, 30, 'zesimo', '8394', 'zesimo-singapore-10gb-30', 490, 'Zesimo phase 5: Singapore 10GB 30 Days', true, true)
  ('singapore-20gb-30', 'SG', 'singapore', 20.0, 30, 'zesimo', '8396', 'zesimo-singapore-20gb-30', 868, 'Zesimo phase 5: Singapore 20GB 30 Days', true, true)
  ('south-korea-5gb-30', 'KR', 'south-korea', 5.0, 30, 'zesimo', '1785', 'zesimo-south-korea-5gb-30', 378, 'Zesimo phase 5: South Korea 5GB 30 Days', true, true)
  ('south-korea-10gb-30', 'KR', 'south-korea', 10.0, 30, 'zesimo', '1786', 'zesimo-south-korea-10gb-30', 658, 'Zesimo phase 5: South Korea 10GB 30 Days', true, true)
  ('south-korea-20gb-30', 'KR', 'south-korea', 20.0, 30, 'zesimo', '2146', 'zesimo-south-korea-20gb-30', 1148, 'Zesimo phase 5: South Korea 20GB 30 Days', true, true)
  ('malaysia-5gb-30', 'MY', 'malaysia', 5.0, 30, 'zesimo', '1739', 'zesimo-malaysia-5gb-30', 378, 'Zesimo phase 5: Malaysia 5GB 30 Days', true, true)
  ('malaysia-10gb-30', 'MY', 'malaysia', 10.0, 30, 'zesimo', '1740', 'zesimo-malaysia-10gb-30', 658, 'Zesimo phase 5: Malaysia 10GB 30 Days', true, true)
  ('malaysia-20gb-30', 'MY', 'malaysia', 20.0, 30, 'zesimo', '2003', 'zesimo-malaysia-20gb-30', 1148, 'Zesimo phase 5: Malaysia 20GB 30 Days', true, true)
  ('australia-1gb-7', 'AU', 'australia', 1.0, 7, 'zesimo', '1620', 'zesimo-australia-1gb-7', 98, 'Zesimo phase 5: Australia 1GB 7 Days', true, true)
  ('australia-3gb-7', 'AU', 'australia', 3.0, 7, 'zesimo', '33', 'zesimo-australia-3gb-7', 347, 'Zesimo phase 5: Australia 3GB 7 Days', true, true)
  ('australia-5gb-15', 'AU', 'australia', 5.0, 15, 'zesimo', '34', 'zesimo-australia-5gb-15', 550, 'Zesimo phase 5: Australia 5GB 15 Days', true, true)
  ('australia-10gb-30', 'AU', 'australia', 10.0, 30, 'zesimo', '2006', 'zesimo-australia-10gb-30', 658, 'Zesimo phase 5: Australia 10GB 30 Days', true, true)
  ('australia-20gb-30', 'AU', 'australia', 20.0, 30, 'zesimo', '8572', 'zesimo-australia-20gb-30', 1134, 'Zesimo phase 5: Australia 20GB 30 Days', true, true)
  ('as-1gb-7', null, 'regional-asia-pacific', 1.0, 7, 'zesimo', '11745', 'zesimo-as-1gb-7', 210, 'Zesimo phase 5: Asia 1GB 7 Days', true, true)
  ('as-3gb-30', null, 'regional-asia-pacific', 3.0, 30, 'zesimo', '11734', 'zesimo-as-3gb-30', 322, 'Zesimo phase 5: Asia 3GB 30 Days', true, true)
  ('eu-3gb-30', null, 'regional-europe', 3.0, 30, 'zesimo', '11705', 'zesimo-eu-3gb-30', 420, 'Zesimo phase 5: Europe 3GB 30 Days', true, true)
  ('gulf-1gb-7', null, 'regional-gulf', 1.0, 7, 'zesimo', '2546', 'zesimo-gulf-1gb-7', 322, 'Zesimo phase 5: Gulf Region 1GB 7 Days', true, true)
  ('gulf-3gb-30', null, 'regional-gulf', 3.0, 30, 'zesimo', '2545', 'zesimo-gulf-3gb-30', 952, 'Zesimo phase 5: Gulf Region 3GB 30 Days', true, true)
  ('gulf-10gb-30', null, 'regional-gulf', 10.0, 30, 'zesimo', '2543', 'zesimo-gulf-10gb-30', 3080, 'Zesimo phase 5: Gulf Region 10GB 30 Days', true, true)
  ('na-20gb-30', null, 'regional-north-america', 20.0, 30, 'zesimo', '588', 'zesimo-na-20gb-30', 2476, 'Zesimo phase 5: North America 20GB 30 Days', true, true)
  ('la-1gb-7', null, 'regional-south-america', 1.0, 7, 'zesimo', '12090', 'zesimo-la-1gb-7', 364, 'Zesimo phase 5: Latin America 1GB 7 Days', true, true)
  ('sa-unlimited-3gb-3d', 'SA', 'saudi-arabia', 3.0, 3, 'zesimo', '10899', 'zesimo-sa-unlimited-3d', 1162, 'Zesimo phase 5: Saudi Arabia Unlimited 3 Days', true, true)
  ('sa-unlimited-3gb-5d', 'SA', 'saudi-arabia', 3.0, 5, 'zesimo', '10901', 'zesimo-sa-unlimited-5d', 1680, 'Zesimo phase 5: Saudi Arabia Unlimited 5 Days', true, true)
  ('sa-unlimited-3gb-15d', 'SA', 'saudi-arabia', 3.0, 15, 'zesimo', '10907', 'zesimo-sa-unlimited-15d', 5152, 'Zesimo phase 5: Saudi Arabia Unlimited 15 Days', true, true)
  ('sa-unlimited-3gb-30d', 'SA', 'saudi-arabia', 3.0, 30, 'zesimo', '10909', 'zesimo-sa-unlimited-30d', 7266, 'Zesimo phase 5: Saudi Arabia Unlimited 30 Days', true, true)
  ('as-unlimited-3d', null, 'regional-asia-pacific', 3.0, 3, 'zesimo', '11759', 'zesimo-as-unlimited-3d', 658, 'Zesimo phase 5: Asia Unlimited 3 Days', true, true)
  ('as-unlimited-5d', null, 'regional-asia-pacific', 3.0, 5, 'zesimo', '11748', 'zesimo-as-unlimited-5d', 924, 'Zesimo phase 5: Asia Unlimited 5 Days', true, true)
  ('as-unlimited-7d', null, 'regional-asia-pacific', 3.0, 7, 'zesimo', '11750', 'zesimo-as-unlimited-7d', 1162, 'Zesimo phase 5: Asia Unlimited 7 Days', true, true)
  ('as-unlimited-10d', null, 'regional-asia-pacific', 3.0, 10, 'zesimo', '11752', 'zesimo-as-unlimited-10d', 1386, 'Zesimo phase 5: Asia Unlimited 10 Days', true, true)
  ('as-unlimited-15d', null, 'regional-asia-pacific', 3.0, 15, 'zesimo', '11757', 'zesimo-as-unlimited-15d', 2674, 'Zesimo phase 5: Asia Unlimited 15 Days', true, true)
  ('eu-uk-1gb-7', null, 'regional-eu-uk', 1.0, 7, 'zesimo', '11675', 'zesimo-eu-uk-1gb-7', 182, 'Zesimo phase 5: European Union and United Kingdom 1GB 7 Days', true, true)
  ('eu-uk-3gb-30', null, 'regional-eu-uk', 3.0, 30, 'zesimo', '11671', 'zesimo-eu-uk-3gb-30', 252, 'Zesimo phase 5: European Union and United Kingdom 3GB 30 Days', true, true)
  ('eu-uk-5gb-30', null, 'regional-eu-uk', 5.0, 30, 'zesimo', '11679', 'zesimo-eu-uk-5gb-30', 336, 'Zesimo phase 5: European Union and United Kingdom 5GB 30 Days', true, true)
  ('eu-uk-10gb-30', null, 'regional-eu-uk', 10.0, 30, 'zesimo', '11673', 'zesimo-eu-uk-10gb-30', 504, 'Zesimo phase 5: European Union and United Kingdom 10GB 30 Days', true, true)
  ('eu-uk-20gb-30', null, 'regional-eu-uk', 20.0, 30, 'zesimo', '11681', 'zesimo-eu-uk-20gb-30', 728, 'Zesimo phase 5: European Union and United Kingdom 20GB 30 Days', true, true)
  ('gl-lite-10gb-30', null, 'regional-global-lite', 10.0, 30, 'zesimo', '7910', 'zesimo-gl-lite-10gb-30', 1612, 'Zesimo phase 5: Global Lite 10GB 30 Days', true, true)
on conflict (catalog_key) do update set
  country_code = excluded.country_code,
  country_slug = excluded.country_slug,
  data_gb = excluded.data_gb,
  validity_days = excluded.validity_days,
  provider = excluded.provider,
  provider_sku = excluded.provider_sku,
  provider_slug = excluded.provider_slug,
  wholesale_cents = excluded.wholesale_cents,
  notes = excluded.notes,
  is_active = true,
  admin_approved = true,
  period_num = null,
  updated_at = now();


-- Retire Telna silent ME rows for countries now on Zesimo Phase 5.
update public.plan_fulfillment_map
set is_active = false, updated_at = now()
where provider = 'telna'
  and country_slug in ('turkey', 'uae', 'egypt', 'qatar', 'kuwait', 'bahrain', 'oman', 'morocco', 'jordan')
  and is_active = true;

-- Retire Australia Telna ladders replaced by Zesimo.
update public.plan_fulfillment_map
set is_active = false, updated_at = now()
where provider = 'telna'
  and (
    catalog_key like 'au-%'
    or country_slug = 'australia'
  )
  and is_active = true;

-- Retire ME regional 1GB/5d Telna if present (storefront now 1GB/7d).
update public.plan_fulfillment_map
set is_active = false, updated_at = now()
where catalog_key = 'me-1gb-5' and is_active = true;


-- Saudi unlimited 3/5 move to Zesimo; add 15/30 catalog plans.
insert into public.mobile_data_plans (
  country_id, name, data_gb, duration_days, wholesale_cost, pricing_strategy,
  plan_category, is_featured, is_active, sort_order, region_id, override_price
)
select v.country_id, v.name, v.data_gb, v.duration_days, v.wholesale_cost,
  v.pricing_strategy::public.pricing_strategy, v.plan_category::public.plan_category,
  v.is_featured, v.is_active, v.sort_order, v.region_id, v.override_price
from (values
  ('saudi-arabia', 'Umrah Unlimited 15 Days', 3::numeric, 15, 51.52, 'MANUAL', 'UNLIMITED', false, true, 38, 'middle-east', 79.99),
  ('saudi-arabia', 'Umrah Unlimited 30 Days', 3::numeric, 30, 72.66, 'MANUAL', 'UNLIMITED', false, true, 39, 'middle-east', 99.99)
) as v(country_id, name, data_gb, duration_days, wholesale_cost, pricing_strategy, plan_category, is_featured, is_active, sort_order, region_id, override_price)
where not exists (
  select 1 from public.mobile_data_plans e
  where e.country_id = v.country_id and e.name = v.name
);

update public.mobile_data_plans
set wholesale_cost = case name
    when 'Umrah Unlimited 3 Days' then 11.62
    when 'Umrah Unlimited 5 Days' then 16.80
    when 'Umrah Unlimited 15 Days' then 51.52
    when 'Umrah Unlimited 30 Days' then 72.66
    else wholesale_cost end,
  override_price = case name
    when 'Umrah Unlimited 3 Days' then 24.99
    when 'Umrah Unlimited 5 Days' then 29.99
    when 'Umrah Unlimited 15 Days' then 79.99
    when 'Umrah Unlimited 30 Days' then 99.99
    else override_price end,
  is_active = true,
  updated_at = now()
where country_id = 'saudi-arabia'
  and name in (
    'Umrah Unlimited 3 Days','Umrah Unlimited 5 Days',
    'Umrah Unlimited 15 Days','Umrah Unlimited 30 Days'
  );


-- Retire unused Telna Asia 3GB/7 that collides with Asia Unlimited 7d (data_gb=3).
update public.plan_fulfillment_map
set is_active = false, updated_at = now()
where catalog_key = 'as-3gb-7' and provider = 'telna' and is_active = true;
