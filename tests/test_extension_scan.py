from openflexure_microscope.api.default_extensions import scan


def test_construct_grid_raster():
    grid = scan.construct_grid((0, 0), (100, 100), (3, 3), style="raster")
    assert grid == [
        [(0, 0), (0, 100), (0, 200)],
        [(100, 0), (100, 100), (100, 200)],
        [(200, 0), (200, 100), (200, 200)],
    ]


def test_construct_grid_snake():
    grid = scan.construct_grid((0, 0), (100, 100), (3, 3), style="snake")
    assert grid == [
        [(0, 0), (0, 100), (0, 200)],
        [(100, 200), (100, 100), (100, 0)],
        [(200, 0), (200, 100), (200, 200)],
    ]


def test_construct_grid_spiral():
    grid = scan.construct_grid((0, 0), (100, 100), (3, 0), style="spiral")
    assert grid == [
        [(0, 0)],
        [
            (0, 100),
            (100, 100),
            (100, 0),
            (100, -100),
            (0, -100),
            (-100, -100),
            (-100, 0),
            (-100, 100),
        ],
        [
            (-100, 200),
            (0, 200),
            (100, 200),
            (200, 200),
            (200, 100),
            (200, 0),
            (200, -100),
            (200, -200),
            (100, -200),
            (0, -200),
            (-100, -200),
            (-200, -200),
            (-200, -100),
            (-200, 0),
            (-200, 100),
            (-200, 200),
        ],
    ]

    # Ensure second n_steps value makes no difference
    assert grid == scan.construct_grid((0, 0), (100, 100), (3, 3), style="spiral")


def test_construct_grid_bogo():
    grid = scan.construct_grid((0, 0), (100, 100), (3, 3), style="bogo")
    positions = [
        (0, 0),
        (0, 100),
        (0, 200),
        (100, 0),
        (100, 100),
        (100, 200),
        (200, 0),
        (200, 100),
        (200, 200),
    ]

    assert len(grid) == 1

    for pos in positions:
        assert pos in grid[0]
