CREATE TABLE daily_aggregates (
    store_id TEXT NOT NULL,
    date DATE NOT NULL,
    unique_users INT,
    sessions INT,
    page_views INT,
    add_to_carts INT,
    checkouts_started INT,
    checkouts_completed INT,
    PRIMARY KEY (store_id, date)
);