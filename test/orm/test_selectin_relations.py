import sqlalchemy as sa
from sqlalchemy import bindparam
from sqlalchemy import ForeignKey
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import Integer
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy import testing
from sqlalchemy.orm import aliased
from sqlalchemy.orm import clear_mappers
from sqlalchemy.orm import create_session
from sqlalchemy.orm import defaultload
from sqlalchemy.orm import defer
from sqlalchemy.orm import deferred
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relationship
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session
from sqlalchemy.orm import subqueryload
from sqlalchemy.orm import undefer
from sqlalchemy.orm import with_polymorphic
from sqlalchemy.testing import assert_raises
from sqlalchemy.testing import assert_raises_message
from sqlalchemy.testing import eq_
from sqlalchemy.testing import fixtures
from sqlalchemy.testing import is_
from sqlalchemy.testing import is_not_
from sqlalchemy.testing import is_true
from sqlalchemy.testing import mock
from sqlalchemy.testing.assertsql import CompiledSQL
from sqlalchemy.testing.schema import Column
from sqlalchemy.testing.schema import Table
from test.orm import _fixtures
from .inheritance._poly_fixtures import _Polymorphic
from .inheritance._poly_fixtures import Company
from .inheritance._poly_fixtures import Engineer
from .inheritance._poly_fixtures import Machine
from .inheritance._poly_fixtures import MachineType
from .inheritance._poly_fixtures import Paperwork
from .inheritance._poly_fixtures import Person


class EagerTest(_fixtures.FixtureTest, testing.AssertsCompiledSQL):
    run_inserts = "once"
    run_deletes = None

    def test_basic(self):
        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    mapper(Address, addresses), order_by=Address.id
                )
            },
        )
        sess = create_session()

        q = sess.query(User).options(selectinload(User.addresses))

        def go():
            eq_(
                [
                    User(
                        id=7,
                        addresses=[
                            Address(id=1, email_address="jack@bean.com")
                        ],
                    )
                ],
                q.filter(User.id == 7).all(),
            )

        self.assert_sql_count(testing.db, go, 2)

        def go():
            eq_(self.static.user_address_result, q.order_by(User.id).all())

        self.assert_sql_count(testing.db, go, 2)

    def test_from_aliased(self):
        users, Dingaling, User, dingalings, Address, addresses = (
            self.tables.users,
            self.classes.Dingaling,
            self.classes.User,
            self.tables.dingalings,
            self.classes.Address,
            self.tables.addresses,
        )

        mapper(Dingaling, dingalings)
        mapper(
            Address,
            addresses,
            properties={
                "dingalings": relationship(Dingaling, order_by=Dingaling.id)
            },
        )
        mapper(
            User,
            users,
            properties={
                "addresses": relationship(Address, order_by=Address.id)
            },
        )
        sess = create_session()

        u = aliased(User)

        q = sess.query(u).options(selectinload(u.addresses))

        def go():
            eq_(
                [
                    User(
                        id=7,
                        addresses=[
                            Address(id=1, email_address="jack@bean.com")
                        ],
                    )
                ],
                q.filter(u.id == 7).all(),
            )

        self.assert_sql_count(testing.db, go, 2)

        def go():
            eq_(self.static.user_address_result, q.order_by(u.id).all())

        self.assert_sql_count(testing.db, go, 2)

        q = sess.query(u).options(
            selectinload(u.addresses).selectinload(Address.dingalings)
        )

        def go():
            eq_(
                [
                    User(
                        id=8,
                        addresses=[
                            Address(
                                id=2,
                                email_address="ed@wood.com",
                                dingalings=[Dingaling()],
                            ),
                            Address(id=3, email_address="ed@bettyboop.com"),
                            Address(id=4, email_address="ed@lala.com"),
                        ],
                    ),
                    User(
                        id=9,
                        addresses=[Address(id=5, dingalings=[Dingaling()])],
                    ),
                ],
                q.filter(u.id.in_([8, 9])).all(),
            )

        self.assert_sql_count(testing.db, go, 3)

    def test_from_get(self):
        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    mapper(Address, addresses), order_by=Address.id
                )
            },
        )
        sess = create_session()

        q = sess.query(User).options(selectinload(User.addresses))

        def go():
            eq_(
                User(
                    id=7,
                    addresses=[Address(id=1, email_address="jack@bean.com")],
                ),
                q.get(7),
            )

        self.assert_sql_count(testing.db, go, 2)

    def test_from_params(self):
        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    mapper(Address, addresses), order_by=Address.id
                )
            },
        )
        sess = create_session()

        q = sess.query(User).options(selectinload(User.addresses))

        def go():
            eq_(
                User(
                    id=7,
                    addresses=[Address(id=1, email_address="jack@bean.com")],
                ),
                q.filter(User.id == bindparam("foo")).params(foo=7).one(),
            )

        self.assert_sql_count(testing.db, go, 2)

    def test_disable_dynamic(self):
        """test no selectin option on a dynamic."""

        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties={"addresses": relationship(Address, lazy="dynamic")},
        )
        mapper(Address, addresses)
        sess = create_session()

        # previously this would not raise, but would emit
        # the query needlessly and put the result nowhere.
        assert_raises_message(
            sa.exc.InvalidRequestError,
            "User.addresses' does not support object population - eager "
            "loading cannot be applied.",
            sess.query(User).options(selectinload(User.addresses)).first,
        )

    def test_many_to_many_plain(self):
        keywords, items, item_keywords, Keyword, Item = (
            self.tables.keywords,
            self.tables.items,
            self.tables.item_keywords,
            self.classes.Keyword,
            self.classes.Item,
        )

        mapper(Keyword, keywords)
        mapper(
            Item,
            items,
            properties=dict(
                keywords=relationship(
                    Keyword,
                    secondary=item_keywords,
                    lazy="selectin",
                    order_by=keywords.c.id,
                )
            ),
        )

        q = create_session().query(Item).order_by(Item.id)

        def go():
            eq_(self.static.item_keyword_result, q.all())

        self.assert_sql_count(testing.db, go, 2)

    def test_many_to_many_with_join(self):
        keywords, items, item_keywords, Keyword, Item = (
            self.tables.keywords,
            self.tables.items,
            self.tables.item_keywords,
            self.classes.Keyword,
            self.classes.Item,
        )

        mapper(Keyword, keywords)
        mapper(
            Item,
            items,
            properties=dict(
                keywords=relationship(
                    Keyword,
                    secondary=item_keywords,
                    lazy="selectin",
                    order_by=keywords.c.id,
                )
            ),
        )

        q = create_session().query(Item).order_by(Item.id)

        def go():
            eq_(
                self.static.item_keyword_result[0:2],
                q.join("keywords").filter(Keyword.name == "red").all(),
            )

        self.assert_sql_count(testing.db, go, 2)

    def test_many_to_many_with_join_alias(self):
        keywords, items, item_keywords, Keyword, Item = (
            self.tables.keywords,
            self.tables.items,
            self.tables.item_keywords,
            self.classes.Keyword,
            self.classes.Item,
        )

        mapper(Keyword, keywords)
        mapper(
            Item,
            items,
            properties=dict(
                keywords=relationship(
                    Keyword,
                    secondary=item_keywords,
                    lazy="selectin",
                    order_by=keywords.c.id,
                )
            ),
        )

        q = create_session().query(Item).order_by(Item.id)

        def go():
            eq_(
                self.static.item_keyword_result[0:2],
                (
                    q.join("keywords", aliased=True).filter(
                        Keyword.name == "red"
                    )
                ).all(),
            )

        self.assert_sql_count(testing.db, go, 2)

    def test_orderby(self):
        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    mapper(Address, addresses),
                    lazy="selectin",
                    order_by=addresses.c.email_address,
                )
            },
        )
        q = create_session().query(User)
        eq_(
            [
                User(id=7, addresses=[Address(id=1)]),
                User(
                    id=8,
                    addresses=[
                        Address(id=3, email_address="ed@bettyboop.com"),
                        Address(id=4, email_address="ed@lala.com"),
                        Address(id=2, email_address="ed@wood.com"),
                    ],
                ),
                User(id=9, addresses=[Address(id=5)]),
                User(id=10, addresses=[]),
            ],
            q.order_by(User.id).all(),
        )

    def test_orderby_multi(self):
        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    mapper(Address, addresses),
                    lazy="selectin",
                    order_by=[addresses.c.email_address, addresses.c.id],
                )
            },
        )
        q = create_session().query(User)
        eq_(
            [
                User(id=7, addresses=[Address(id=1)]),
                User(
                    id=8,
                    addresses=[
                        Address(id=3, email_address="ed@bettyboop.com"),
                        Address(id=4, email_address="ed@lala.com"),
                        Address(id=2, email_address="ed@wood.com"),
                    ],
                ),
                User(id=9, addresses=[Address(id=5)]),
                User(id=10, addresses=[]),
            ],
            q.order_by(User.id).all(),
        )

    def test_orderby_related(self):
        """A regular mapper select on a single table can
            order by a relationship to a second table"""

        Address, addresses, users, User = (
            self.classes.Address,
            self.tables.addresses,
            self.tables.users,
            self.classes.User,
        )

        mapper(Address, addresses)
        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address, lazy="selectin", order_by=addresses.c.id
                )
            ),
        )

        q = create_session().query(User)
        result = (
            q.filter(User.id == Address.user_id)
            .order_by(Address.email_address)
            .all()
        )

        eq_(
            [
                User(
                    id=8,
                    addresses=[
                        Address(id=2, email_address="ed@wood.com"),
                        Address(id=3, email_address="ed@bettyboop.com"),
                        Address(id=4, email_address="ed@lala.com"),
                    ],
                ),
                User(id=9, addresses=[Address(id=5)]),
                User(id=7, addresses=[Address(id=1)]),
            ],
            result,
        )

    def test_orderby_desc(self):
        Address, addresses, users, User = (
            self.classes.Address,
            self.tables.addresses,
            self.tables.users,
            self.classes.User,
        )

        mapper(Address, addresses)
        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address,
                    lazy="selectin",
                    order_by=[sa.desc(addresses.c.email_address)],
                )
            ),
        )
        sess = create_session()
        eq_(
            [
                User(id=7, addresses=[Address(id=1)]),
                User(
                    id=8,
                    addresses=[
                        Address(id=2, email_address="ed@wood.com"),
                        Address(id=4, email_address="ed@lala.com"),
                        Address(id=3, email_address="ed@bettyboop.com"),
                    ],
                ),
                User(id=9, addresses=[Address(id=5)]),
                User(id=10, addresses=[]),
            ],
            sess.query(User).order_by(User.id).all(),
        )

    _pathing_runs = [
        ("lazyload", "lazyload", "lazyload", 15),
        ("selectinload", "lazyload", "lazyload", 12),
        ("selectinload", "selectinload", "lazyload", 8),
        ("joinedload", "selectinload", "lazyload", 7),
        ("lazyload", "lazyload", "selectinload", 12),
        ("selectinload", "selectinload", "selectinload", 4),
        ("selectinload", "selectinload", "joinedload", 3),
    ]

    def test_options_pathing(self):
        self._do_options_test(self._pathing_runs)

    def test_mapper_pathing(self):
        self._do_mapper_test(self._pathing_runs)

    def _do_options_test(self, configs):
        (
            users,
            Keyword,
            orders,
            items,
            order_items,
            Order,
            Item,
            User,
            keywords,
            item_keywords,
        ) = (
            self.tables.users,
            self.classes.Keyword,
            self.tables.orders,
            self.tables.items,
            self.tables.order_items,
            self.classes.Order,
            self.classes.Item,
            self.classes.User,
            self.tables.keywords,
            self.tables.item_keywords,
        )

        mapper(
            User,
            users,
            properties={
                "orders": relationship(Order, order_by=orders.c.id)  # o2m, m2o
            },
        )
        mapper(
            Order,
            orders,
            properties={
                "items": relationship(
                    Item, secondary=order_items, order_by=items.c.id
                )  # m2m
            },
        )
        mapper(
            Item,
            items,
            properties={
                "keywords": relationship(
                    Keyword, secondary=item_keywords, order_by=keywords.c.id
                )  # m2m
            },
        )
        mapper(Keyword, keywords)

        callables = {
            "joinedload": joinedload,
            "selectinload": selectinload,
            "subqueryload": subqueryload,
        }

        for o, i, k, count in configs:
            options = []
            if o in callables:
                options.append(callables[o](User.orders))
            if i in callables:
                options.append(callables[i](User.orders, Order.items))
            if k in callables:
                options.append(
                    callables[k](User.orders, Order.items, Item.keywords)
                )

            self._do_query_tests(options, count)

    def _do_mapper_test(self, configs):
        (
            users,
            Keyword,
            orders,
            items,
            order_items,
            Order,
            Item,
            User,
            keywords,
            item_keywords,
        ) = (
            self.tables.users,
            self.classes.Keyword,
            self.tables.orders,
            self.tables.items,
            self.tables.order_items,
            self.classes.Order,
            self.classes.Item,
            self.classes.User,
            self.tables.keywords,
            self.tables.item_keywords,
        )

        opts = {
            "lazyload": "select",
            "joinedload": "joined",
            "selectinload": "selectin",
        }

        for o, i, k, count in configs:
            mapper(
                User,
                users,
                properties={
                    "orders": relationship(
                        Order, lazy=opts[o], order_by=orders.c.id
                    )
                },
            )
            mapper(
                Order,
                orders,
                properties={
                    "items": relationship(
                        Item,
                        secondary=order_items,
                        lazy=opts[i],
                        order_by=items.c.id,
                    )
                },
            )
            mapper(
                Item,
                items,
                properties={
                    "keywords": relationship(
                        Keyword,
                        lazy=opts[k],
                        secondary=item_keywords,
                        order_by=keywords.c.id,
                    )
                },
            )
            mapper(Keyword, keywords)

            try:
                self._do_query_tests([], count)
            finally:
                clear_mappers()

    def _do_query_tests(self, opts, count):
        Order, User = self.classes.Order, self.classes.User

        sess = create_session()

        def go():
            eq_(
                sess.query(User).options(*opts).order_by(User.id).all(),
                self.static.user_item_keyword_result,
            )

        self.assert_sql_count(testing.db, go, count)

        eq_(
            sess.query(User)
            .options(*opts)
            .filter(User.name == "fred")
            .order_by(User.id)
            .all(),
            self.static.user_item_keyword_result[2:3],
        )

        sess = create_session()
        eq_(
            sess.query(User)
            .options(*opts)
            .join(User.orders)
            .filter(Order.id == 3)
            .order_by(User.id)
            .all(),
            self.static.user_item_keyword_result[0:1],
        )

    def test_cyclical(self):
        """A circular eager relationship breaks the cycle with a lazy loader"""

        Address, addresses, users, User = (
            self.classes.Address,
            self.tables.addresses,
            self.tables.users,
            self.classes.User,
        )

        mapper(Address, addresses)
        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address,
                    lazy="selectin",
                    backref=sa.orm.backref("user", lazy="selectin"),
                    order_by=Address.id,
                )
            ),
        )
        is_(
            sa.orm.class_mapper(User).get_property("addresses").lazy,
            "selectin",
        )
        is_(sa.orm.class_mapper(Address).get_property("user").lazy, "selectin")

        sess = create_session()
        eq_(
            self.static.user_address_result,
            sess.query(User).order_by(User.id).all(),
        )

    def test_cyclical_explicit_join_depth(self):
        """A circular eager relationship breaks the cycle with a lazy loader"""

        Address, addresses, users, User = (
            self.classes.Address,
            self.tables.addresses,
            self.tables.users,
            self.classes.User,
        )

        mapper(Address, addresses)
        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address,
                    lazy="selectin",
                    join_depth=1,
                    backref=sa.orm.backref(
                        "user", lazy="selectin", join_depth=1
                    ),
                    order_by=Address.id,
                )
            ),
        )
        is_(
            sa.orm.class_mapper(User).get_property("addresses").lazy,
            "selectin",
        )
        is_(sa.orm.class_mapper(Address).get_property("user").lazy, "selectin")

        sess = create_session()
        eq_(
            self.static.user_address_result,
            sess.query(User).order_by(User.id).all(),
        )

    def test_double_w_ac_against_subquery(self):

        (
            users,
            orders,
            User,
            Address,
            Order,
            addresses,
            Item,
            items,
            order_items,
        ) = (
            self.tables.users,
            self.tables.orders,
            self.classes.User,
            self.classes.Address,
            self.classes.Order,
            self.tables.addresses,
            self.classes.Item,
            self.tables.items,
            self.tables.order_items,
        )

        mapper(Address, addresses)
        mapper(
            Order,
            orders,
            properties={
                "items": relationship(
                    Item,
                    secondary=order_items,
                    lazy="selectin",
                    order_by=items.c.id,
                )
            },
        )
        mapper(Item, items)

        open_mapper = aliased(
            Order, select([orders]).where(orders.c.isopen == 1).alias()
        )
        closed_mapper = aliased(
            Order, select([orders]).where(orders.c.isopen == 0).alias()
        )

        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address, lazy="selectin", order_by=addresses.c.id
                ),
                open_orders=relationship(
                    open_mapper, lazy="selectin", order_by=open_mapper.id
                ),
                closed_orders=relationship(
                    closed_mapper, lazy="selectin", order_by=closed_mapper.id
                ),
            ),
        )

        self._run_double_test()

    def test_double_w_ac(self):

        (
            users,
            orders,
            User,
            Address,
            Order,
            addresses,
            Item,
            items,
            order_items,
        ) = (
            self.tables.users,
            self.tables.orders,
            self.classes.User,
            self.classes.Address,
            self.classes.Order,
            self.tables.addresses,
            self.classes.Item,
            self.tables.items,
            self.tables.order_items,
        )

        mapper(Address, addresses)
        mapper(
            Order,
            orders,
            properties={
                "items": relationship(
                    Item,
                    secondary=order_items,
                    lazy="selectin",
                    order_by=items.c.id,
                )
            },
        )
        mapper(Item, items)

        open_mapper = aliased(Order, orders)
        closed_mapper = aliased(Order, orders)

        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address, lazy="selectin", order_by=addresses.c.id
                ),
                open_orders=relationship(
                    open_mapper,
                    primaryjoin=sa.and_(
                        open_mapper.isopen == 1,
                        users.c.id == open_mapper.user_id,
                    ),
                    lazy="selectin",
                    order_by=open_mapper.id,
                ),
                closed_orders=relationship(
                    closed_mapper,
                    primaryjoin=sa.and_(
                        closed_mapper.isopen == 0,
                        users.c.id == closed_mapper.user_id,
                    ),
                    lazy="selectin",
                    order_by=closed_mapper.id,
                ),
            ),
        )

        self._run_double_test()

    def test_double_same_mappers(self):
        """Eager loading with two relationships simultaneously,
        from the same table, using aliases."""

        (
            addresses,
            items,
            order_items,
            orders,
            Item,
            User,
            Address,
            Order,
            users,
        ) = (
            self.tables.addresses,
            self.tables.items,
            self.tables.order_items,
            self.tables.orders,
            self.classes.Item,
            self.classes.User,
            self.classes.Address,
            self.classes.Order,
            self.tables.users,
        )

        mapper(Address, addresses)
        mapper(
            Order,
            orders,
            properties={
                "items": relationship(
                    Item,
                    secondary=order_items,
                    lazy="selectin",
                    order_by=items.c.id,
                )
            },
        )
        mapper(Item, items)
        mapper(
            User,
            users,
            properties=dict(
                addresses=relationship(
                    Address, lazy="selectin", order_by=addresses.c.id
                ),
                open_orders=relationship(
                    Order,
                    primaryjoin=sa.and_(
                        orders.c.isopen == 1, users.c.id == orders.c.user_id
                    ),
                    lazy="selectin",
                    order_by=orders.c.id,
                ),
                closed_orders=relationship(
                    Order,
                    primaryjoin=sa.and_(
                        orders.c.isopen == 0, users.c.id == orders.c.user_id
                    ),
                    lazy="selectin",
                    order_by=orders.c.id,
                ),
            ),
        )

        self._run_double_test()

    def _run_double_test(self, no_items=False):
        User, Address, Order, Item = self.classes(
            "User", "Address", "Order", "Item"
        )
        q = create_session().query(User).order_by(User.id)

        def items(*ids):
            if no_items:
                return {}
            else:
                return {"items": [Item(id=id_) for id_ in ids]}

        def go():
            eq_(
                [
                    User(
                        id=7,
                        addresses=[Address(id=1)],
                        open_orders=[Order(id=3, **items(3, 4, 5))],
                        closed_orders=[
                            Order(id=1, **items(1, 2, 3)),
                            Order(id=5, **items(5)),
                        ],
                    ),
                    User(
                        id=8,
                        addresses=[
                            Address(id=2),
                            Address(id=3),
                            Address(id=4),
                        ],
                        open_orders=[],
                        closed_orders=[],
                    ),
                    User(
                        id=9,
                        addresses=[Address(id=5)],
                        open_orders=[Order(id=4, **items(1, 5))],
                        closed_orders=[Order(id=2, **items(1, 2, 3))],
                    ),
                    User(id=10),
                ],
                q.all(),
            )

        if no_items:
            self.assert_sql_count(testing.db, go, 4)
        else:
            self.assert_sql_count(testing.db, go, 6)

    def test_limit(self):
        """Limit operations combined with lazy-load relationships."""

        (
            users,
            items,
            order_items,
            orders,
            Item,
            User,
            Address,
            Order,
            addresses,
        ) = (
            self.tables.users,
            self.tables.items,
            self.tables.order_items,
            self.tables.orders,
            self.classes.Item,
            self.classes.User,
            self.classes.Address,
            self.classes.Order,
            self.tables.addresses,
        )

        mapper(Item, items)
        mapper(
            Order,
            orders,
            properties={
                "items": relationship(
                    Item,
                    secondary=order_items,
                    lazy="selectin",
                    order_by=items.c.id,
                )
            },
        )
        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    mapper(Address, addresses),
                    lazy="selectin",
                    order_by=addresses.c.id,
                ),
                "orders": relationship(
                    Order, lazy="select", order_by=orders.c.id
                ),
            },
        )

        sess = create_session()
        q = sess.query(User)

        result = q.order_by(User.id).limit(2).offset(1).all()
        eq_(self.static.user_all_result[1:3], result)

        result = q.order_by(sa.desc(User.id)).limit(2).offset(2).all()
        eq_(list(reversed(self.static.user_all_result[0:2])), result)

    def test_one_to_many_scalar(self):
        Address, addresses, users, User = (
            self.classes.Address,
            self.tables.addresses,
            self.tables.users,
            self.classes.User,
        )

        mapper(
            User,
            users,
            properties=dict(
                address=relationship(
                    mapper(Address, addresses), lazy="selectin", uselist=False
                )
            ),
        )
        q = create_session().query(User)

        def go():
            result = q.filter(users.c.id == 7).all()
            eq_([User(id=7, address=Address(id=1))], result)

        self.assert_sql_count(testing.db, go, 2)

    def test_many_to_one(self):
        users, Address, addresses, User = (
            self.tables.users,
            self.classes.Address,
            self.tables.addresses,
            self.classes.User,
        )

        mapper(
            Address,
            addresses,
            properties=dict(
                user=relationship(mapper(User, users), lazy="selectin")
            ),
        )
        sess = create_session()
        q = sess.query(Address)

        def go():
            a = q.filter(addresses.c.id == 1).one()
            is_not_(a.user, None)
            u1 = sess.query(User).get(7)
            is_(a.user, u1)

        self.assert_sql_count(testing.db, go, 2)

    def test_double_with_aggregate(self):
        User, users, orders, Order = (
            self.classes.User,
            self.tables.users,
            self.tables.orders,
            self.classes.Order,
        )

        max_orders_by_user = sa.select(
            [sa.func.max(orders.c.id).label("order_id")],
            group_by=[orders.c.user_id],
        ).alias("max_orders_by_user")

        max_orders = orders.select(
            orders.c.id == max_orders_by_user.c.order_id
        ).alias("max_orders")

        mapper(Order, orders)
        mapper(
            User,
            users,
            properties={
                "orders": relationship(
                    Order,
                    backref="user",
                    lazy="selectin",
                    order_by=orders.c.id,
                ),
                "max_order": relationship(
                    aliased(Order, max_orders), lazy="selectin", uselist=False
                ),
            },
        )

        q = create_session().query(User)

        def go():
            eq_(
                [
                    User(
                        id=7,
                        orders=[Order(id=1), Order(id=3), Order(id=5)],
                        max_order=Order(id=5),
                    ),
                    User(id=8, orders=[]),
                    User(
                        id=9,
                        orders=[Order(id=2), Order(id=4)],
                        max_order=Order(id=4),
                    ),
                    User(id=10),
                ],
                q.order_by(User.id).all(),
            )

        self.assert_sql_count(testing.db, go, 3)

    def test_uselist_false_warning(self):
        """test that multiple rows received by a
        uselist=False raises a warning."""

        User, users, orders, Order = (
            self.classes.User,
            self.tables.users,
            self.tables.orders,
            self.classes.Order,
        )

        mapper(
            User,
            users,
            properties={"order": relationship(Order, uselist=False)},
        )
        mapper(Order, orders)
        s = create_session()
        assert_raises(
            sa.exc.SAWarning,
            s.query(User).options(selectinload(User.order)).all,
        )


class LoadOnExistingTest(_fixtures.FixtureTest):
    """test that loaders from a base Query fully populate."""

    run_inserts = "once"
    run_deletes = None

    def _collection_to_scalar_fixture(self):
        User, Address, Dingaling = (
            self.classes.User,
            self.classes.Address,
            self.classes.Dingaling,
        )
        mapper(
            User,
            self.tables.users,
            properties={"addresses": relationship(Address)},
        )
        mapper(
            Address,
            self.tables.addresses,
            properties={"dingaling": relationship(Dingaling)},
        )
        mapper(Dingaling, self.tables.dingalings)

        sess = Session(autoflush=False)
        return User, Address, Dingaling, sess

    def _collection_to_collection_fixture(self):
        User, Order, Item = (
            self.classes.User,
            self.classes.Order,
            self.classes.Item,
        )
        mapper(
            User, self.tables.users, properties={"orders": relationship(Order)}
        )
        mapper(
            Order,
            self.tables.orders,
            properties={
                "items": relationship(Item, secondary=self.tables.order_items)
            },
        )
        mapper(Item, self.tables.items)

        sess = Session(autoflush=False)
        return User, Order, Item, sess

    def _eager_config_fixture(self):
        User, Address = self.classes.User, self.classes.Address
        mapper(
            User,
            self.tables.users,
            properties={"addresses": relationship(Address, lazy="selectin")},
        )
        mapper(Address, self.tables.addresses)
        sess = Session(autoflush=False)
        return User, Address, sess

    def _deferred_config_fixture(self):
        User, Address = self.classes.User, self.classes.Address
        mapper(
            User,
            self.tables.users,
            properties={
                "name": deferred(self.tables.users.c.name),
                "addresses": relationship(Address, lazy="selectin"),
            },
        )
        mapper(Address, self.tables.addresses)
        sess = Session(autoflush=False)
        return User, Address, sess

    def test_no_query_on_refresh(self):
        User, Address, sess = self._eager_config_fixture()

        u1 = sess.query(User).get(8)
        assert "addresses" in u1.__dict__
        sess.expire(u1)

        def go():
            eq_(u1.id, 8)

        self.assert_sql_count(testing.db, go, 1)
        assert "addresses" not in u1.__dict__

    def test_no_query_on_deferred(self):
        User, Address, sess = self._deferred_config_fixture()
        u1 = sess.query(User).get(8)
        assert "addresses" in u1.__dict__
        sess.expire(u1, ["addresses"])

        def go():
            eq_(u1.name, "ed")

        self.assert_sql_count(testing.db, go, 1)
        assert "addresses" not in u1.__dict__

    def test_populate_existing_propagate(self):
        User, Address, sess = self._eager_config_fixture()
        u1 = sess.query(User).get(8)
        u1.addresses[2].email_address = "foofoo"
        del u1.addresses[1]
        u1 = sess.query(User).populate_existing().filter_by(id=8).one()
        # collection is reverted
        eq_(len(u1.addresses), 3)

        # attributes on related items reverted
        eq_(u1.addresses[2].email_address, "ed@lala.com")

    def test_loads_second_level_collection_to_scalar(self):
        User, Address, Dingaling, sess = self._collection_to_scalar_fixture()

        u1 = sess.query(User).get(8)
        a1 = Address()
        u1.addresses.append(a1)
        a2 = u1.addresses[0]
        a2.email_address = "foo"
        sess.query(User).options(
            selectinload("addresses").selectinload("dingaling")
        ).filter_by(id=8).all()
        assert u1.addresses[-1] is a1
        for a in u1.addresses:
            if a is not a1:
                assert "dingaling" in a.__dict__
            else:
                assert "dingaling" not in a.__dict__
            if a is a2:
                eq_(a2.email_address, "foo")

    def test_loads_second_level_collection_to_collection(self):
        User, Order, Item, sess = self._collection_to_collection_fixture()

        u1 = sess.query(User).get(7)
        u1.orders
        o1 = Order()
        u1.orders.append(o1)
        sess.query(User).options(
            selectinload("orders").selectinload("items")
        ).filter_by(id=7).all()
        for o in u1.orders:
            if o is not o1:
                assert "items" in o.__dict__
            else:
                assert "items" not in o.__dict__

    def test_load_two_levels_collection_to_scalar(self):
        User, Address, Dingaling, sess = self._collection_to_scalar_fixture()

        u1 = (
            sess.query(User)
            .filter_by(id=8)
            .options(selectinload("addresses"))
            .one()
        )
        sess.query(User).filter_by(id=8).options(
            selectinload("addresses").selectinload("dingaling")
        ).first()
        assert "dingaling" in u1.addresses[0].__dict__

    def test_load_two_levels_collection_to_collection(self):
        User, Order, Item, sess = self._collection_to_collection_fixture()

        u1 = (
            sess.query(User)
            .filter_by(id=7)
            .options(selectinload("orders"))
            .one()
        )
        sess.query(User).filter_by(id=7).options(
            selectinload("orders").selectinload("items")
        ).first()
        assert "items" in u1.orders[0].__dict__


class OrderBySecondaryTest(fixtures.MappedTest):
    @classmethod
    def define_tables(cls, metadata):
        Table(
            "m2m",
            metadata,
            Column(
                "id", Integer, primary_key=True, test_needs_autoincrement=True
            ),
            Column("aid", Integer, ForeignKey("a.id")),
            Column("bid", Integer, ForeignKey("b.id")),
        )

        Table(
            "a",
            metadata,
            Column(
                "id", Integer, primary_key=True, test_needs_autoincrement=True
            ),
            Column("data", String(50)),
        )
        Table(
            "b",
            metadata,
            Column(
                "id", Integer, primary_key=True, test_needs_autoincrement=True
            ),
            Column("data", String(50)),
        )

    @classmethod
    def fixtures(cls):
        return dict(
            a=(("id", "data"), (1, "a1"), (2, "a2")),
            b=(("id", "data"), (1, "b1"), (2, "b2"), (3, "b3"), (4, "b4")),
            m2m=(
                ("id", "aid", "bid"),
                (2, 1, 1),
                (4, 2, 4),
                (1, 1, 3),
                (6, 2, 2),
                (3, 1, 2),
                (5, 2, 3),
            ),
        )

    def test_ordering(self):
        a, m2m, b = (self.tables.a, self.tables.m2m, self.tables.b)

        class A(fixtures.ComparableEntity):
            pass

        class B(fixtures.ComparableEntity):
            pass

        mapper(
            A,
            a,
            properties={
                "bs": relationship(
                    B, secondary=m2m, lazy="selectin", order_by=m2m.c.id
                )
            },
        )
        mapper(B, b)

        sess = create_session()

        def go():
            eq_(
                sess.query(A).all(),
                [
                    A(
                        data="a1",
                        bs=[B(data="b3"), B(data="b1"), B(data="b2")],
                    ),
                    A(bs=[B(data="b4"), B(data="b3"), B(data="b2")]),
                ],
            )

        self.assert_sql_count(testing.db, go, 2)


class BaseRelationFromJoinedSubclassTest(_Polymorphic):
    """Like most tests here, this is adapted from subquery_relations
    as part of general inheritance testing.

    The subquery test exercised the issue that the subquery load must
    imitate the original query very closely so that filter criteria, ordering
    etc. can be maintained with the original query embedded.   However,
    for selectin loading, none of that is really needed, so here the secondary
    queries are all just a simple "people JOIN paperwork".

    """

    @classmethod
    def define_tables(cls, metadata):
        Table(
            "people",
            metadata,
            Column(
                "person_id",
                Integer,
                primary_key=True,
                test_needs_autoincrement=True,
            ),
            Column("name", String(50)),
            Column("type", String(30)),
        )

        # to test fully, PK of engineers table must be
        # named differently from that of people
        Table(
            "engineers",
            metadata,
            Column(
                "engineer_id",
                Integer,
                ForeignKey("people.person_id"),
                primary_key=True,
            ),
            Column("primary_language", String(50)),
        )

        Table(
            "paperwork",
            metadata,
            Column(
                "paperwork_id",
                Integer,
                primary_key=True,
                test_needs_autoincrement=True,
            ),
            Column("description", String(50)),
            Column("person_id", Integer, ForeignKey("people.person_id")),
        )

    @classmethod
    def setup_mappers(cls):
        people = cls.tables.people
        engineers = cls.tables.engineers
        paperwork = cls.tables.paperwork

        mapper(
            Person,
            people,
            polymorphic_on=people.c.type,
            polymorphic_identity="person",
            properties={
                "paperwork": relationship(
                    Paperwork, order_by=paperwork.c.paperwork_id
                )
            },
        )

        mapper(
            Engineer,
            engineers,
            inherits=Person,
            polymorphic_identity="engineer",
        )

        mapper(Paperwork, paperwork)

    @classmethod
    def insert_data(cls):

        e1 = Engineer(primary_language="java")
        e2 = Engineer(primary_language="c++")
        e1.paperwork = [
            Paperwork(description="tps report #1"),
            Paperwork(description="tps report #2"),
        ]
        e2.paperwork = [Paperwork(description="tps report #3")]
        sess = create_session()
        sess.add_all([e1, e2])
        sess.flush()

    def test_correct_select_nofrom(self):
        sess = create_session()
        # use Person.paperwork here just to give the least
        # amount of context
        q = (
            sess.query(Engineer)
            .filter(Engineer.primary_language == "java")
            .options(selectinload(Person.paperwork))
        )

        def go():
            eq_(
                q.all()[0].paperwork,
                [
                    Paperwork(description="tps report #1"),
                    Paperwork(description="tps report #2"),
                ],
            )

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT people.person_id AS people_person_id, "
                "people.name AS people_name, people.type AS people_type, "
                "engineers.engineer_id AS engineers_engineer_id, "
                "engineers.primary_language AS engineers_primary_language "
                "FROM people JOIN engineers ON "
                "people.person_id = engineers.engineer_id "
                "WHERE engineers.primary_language = :primary_language_1",
                {"primary_language_1": "java"},
            ),
            CompiledSQL(
                "SELECT paperwork.person_id AS paperwork_person_id, "
                "paperwork.paperwork_id AS paperwork_paperwork_id, "
                "paperwork.description AS paperwork_description "
                "FROM paperwork WHERE paperwork.person_id "
                "IN ([EXPANDING_primary_keys]) "
                "ORDER BY paperwork.person_id, paperwork.paperwork_id",
                [{"primary_keys": [1]}],
            ),
        )

    def test_correct_select_existingfrom(self):
        sess = create_session()
        # use Person.paperwork here just to give the least
        # amount of context
        q = (
            sess.query(Engineer)
            .filter(Engineer.primary_language == "java")
            .join(Engineer.paperwork)
            .filter(Paperwork.description == "tps report #2")
            .options(selectinload(Person.paperwork))
        )

        def go():
            eq_(
                q.one().paperwork,
                [
                    Paperwork(description="tps report #1"),
                    Paperwork(description="tps report #2"),
                ],
            )

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT people.person_id AS people_person_id, "
                "people.name AS people_name, people.type AS people_type, "
                "engineers.engineer_id AS engineers_engineer_id, "
                "engineers.primary_language AS engineers_primary_language "
                "FROM people JOIN engineers "
                "ON people.person_id = engineers.engineer_id "
                "JOIN paperwork ON people.person_id = paperwork.person_id "
                "WHERE engineers.primary_language = :primary_language_1 "
                "AND paperwork.description = :description_1",
                {
                    "primary_language_1": "java",
                    "description_1": "tps report #2",
                },
            ),
            CompiledSQL(
                "SELECT paperwork.person_id AS paperwork_person_id, "
                "paperwork.paperwork_id AS paperwork_paperwork_id, "
                "paperwork.description AS paperwork_description "
                "FROM paperwork WHERE paperwork.person_id "
                "IN ([EXPANDING_primary_keys]) "
                "ORDER BY paperwork.person_id, paperwork.paperwork_id",
                [{"primary_keys": [1]}],
            ),
        )

    def test_correct_select_with_polymorphic_no_alias(self):
        # test #3106
        sess = create_session()

        wp = with_polymorphic(Person, [Engineer])
        q = (
            sess.query(wp)
            .options(selectinload(wp.paperwork))
            .order_by(Engineer.primary_language.desc())
        )

        def go():
            eq_(
                q.first(),
                Engineer(
                    paperwork=[
                        Paperwork(description="tps report #1"),
                        Paperwork(description="tps report #2"),
                    ],
                    primary_language="java",
                ),
            )

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT people.person_id AS people_person_id, "
                "people.name AS people_name, people.type AS people_type, "
                "engineers.engineer_id AS engineers_engineer_id, "
                "engineers.primary_language AS engineers_primary_language "
                "FROM people LEFT OUTER JOIN engineers ON people.person_id = "
                "engineers.engineer_id ORDER BY engineers.primary_language "
                "DESC LIMIT :param_1"
            ),
            CompiledSQL(
                "SELECT paperwork.person_id AS paperwork_person_id, "
                "paperwork.paperwork_id AS paperwork_paperwork_id, "
                "paperwork.description AS paperwork_description "
                "FROM paperwork WHERE paperwork.person_id "
                "IN ([EXPANDING_primary_keys]) "
                "ORDER BY paperwork.person_id, paperwork.paperwork_id",
                [{"primary_keys": [1]}],
            ),
        )

    def test_correct_select_with_polymorphic_alias(self):
        # test #3106
        sess = create_session()

        wp = with_polymorphic(Person, [Engineer], aliased=True)
        q = (
            sess.query(wp)
            .options(selectinload(wp.paperwork))
            .order_by(wp.Engineer.primary_language.desc())
        )

        def go():
            eq_(
                q.first(),
                Engineer(
                    paperwork=[
                        Paperwork(description="tps report #1"),
                        Paperwork(description="tps report #2"),
                    ],
                    primary_language="java",
                ),
            )

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT anon_1.people_person_id AS anon_1_people_person_id, "
                "anon_1.people_name AS anon_1_people_name, "
                "anon_1.people_type AS anon_1_people_type, "
                "anon_1.engineers_engineer_id AS "
                "anon_1_engineers_engineer_id, "
                "anon_1.engineers_primary_language "
                "AS anon_1_engineers_primary_language FROM "
                "(SELECT people.person_id AS people_person_id, "
                "people.name AS people_name, people.type AS people_type, "
                "engineers.engineer_id AS engineers_engineer_id, "
                "engineers.primary_language AS engineers_primary_language "
                "FROM people LEFT OUTER JOIN engineers ON people.person_id = "
                "engineers.engineer_id) AS anon_1 "
                "ORDER BY anon_1.engineers_primary_language DESC "
                "LIMIT :param_1"
            ),
            CompiledSQL(
                "SELECT paperwork.person_id AS paperwork_person_id, "
                "paperwork.paperwork_id AS paperwork_paperwork_id, "
                "paperwork.description AS paperwork_description "
                "FROM paperwork WHERE paperwork.person_id "
                "IN ([EXPANDING_primary_keys]) "
                "ORDER BY paperwork.person_id, paperwork.paperwork_id",
                [{"primary_keys": [1]}],
            ),
        )

    def test_correct_select_with_polymorphic_flat_alias(self):
        # test #3106
        sess = create_session()

        wp = with_polymorphic(Person, [Engineer], aliased=True, flat=True)
        q = (
            sess.query(wp)
            .options(selectinload(wp.paperwork))
            .order_by(wp.Engineer.primary_language.desc())
        )

        def go():
            eq_(
                q.first(),
                Engineer(
                    paperwork=[
                        Paperwork(description="tps report #1"),
                        Paperwork(description="tps report #2"),
                    ],
                    primary_language="java",
                ),
            )

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT people_1.person_id AS people_1_person_id, "
                "people_1.name AS people_1_name, "
                "people_1.type AS people_1_type, "
                "engineers_1.engineer_id AS engineers_1_engineer_id, "
                "engineers_1.primary_language AS engineers_1_primary_language "
                "FROM people AS people_1 "
                "LEFT OUTER JOIN engineers AS engineers_1 "
                "ON people_1.person_id = engineers_1.engineer_id "
                "ORDER BY engineers_1.primary_language DESC LIMIT :param_1"
            ),
            CompiledSQL(
                "SELECT paperwork.person_id AS paperwork_person_id, "
                "paperwork.paperwork_id AS paperwork_paperwork_id, "
                "paperwork.description AS paperwork_description "
                "FROM paperwork WHERE paperwork.person_id "
                "IN ([EXPANDING_primary_keys]) "
                "ORDER BY paperwork.person_id, paperwork.paperwork_id",
                [{"primary_keys": [1]}],
            ),
        )


class HeterogeneousSubtypesTest(fixtures.DeclarativeMappedTest):
    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class Company(Base):
            __tablename__ = "company"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            employees = relationship("Employee", order_by="Employee.id")

        class Employee(Base):
            __tablename__ = "employee"
            id = Column(Integer, primary_key=True)
            type = Column(String(50))
            name = Column(String(50))
            company_id = Column(ForeignKey("company.id"))

            __mapper_args__ = {
                "polymorphic_on": "type",
                "with_polymorphic": "*",
            }

        class Programmer(Employee):
            __tablename__ = "programmer"
            id = Column(ForeignKey("employee.id"), primary_key=True)
            languages = relationship("Language")

            __mapper_args__ = {"polymorphic_identity": "programmer"}

        class Manager(Employee):
            __tablename__ = "manager"
            id = Column(ForeignKey("employee.id"), primary_key=True)
            golf_swing_id = Column(ForeignKey("golf_swing.id"))
            golf_swing = relationship("GolfSwing")

            __mapper_args__ = {"polymorphic_identity": "manager"}

        class Language(Base):
            __tablename__ = "language"
            id = Column(Integer, primary_key=True)
            programmer_id = Column(
                Integer, ForeignKey("programmer.id"), nullable=False
            )
            name = Column(String(50))

        class GolfSwing(Base):
            __tablename__ = "golf_swing"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

    @classmethod
    def insert_data(cls):
        Company, Programmer, Manager, GolfSwing, Language = cls.classes(
            "Company", "Programmer", "Manager", "GolfSwing", "Language"
        )
        c1 = Company(
            id=1,
            name="Foobar Corp",
            employees=[
                Programmer(
                    id=1, name="p1", languages=[Language(id=1, name="Python")]
                ),
                Manager(id=2, name="m1", golf_swing=GolfSwing(name="fore")),
            ],
        )
        c2 = Company(
            id=2,
            name="bat Corp",
            employees=[
                Manager(id=3, name="m2", golf_swing=GolfSwing(name="clubs")),
                Programmer(
                    id=4, name="p2", languages=[Language(id=2, name="Java")]
                ),
            ],
        )
        sess = Session()
        sess.add_all([c1, c2])
        sess.commit()

    def test_one_to_many(self):

        Company, Programmer, Manager, GolfSwing, Language = self.classes(
            "Company", "Programmer", "Manager", "GolfSwing", "Language"
        )
        sess = Session()
        company = (
            sess.query(Company)
            .filter(Company.id == 1)
            .options(
                selectinload(
                    Company.employees.of_type(Programmer)
                ).selectinload(Programmer.languages)
            )
            .one()
        )

        def go():
            eq_(company.employees[0].languages[0].name, "Python")

        self.assert_sql_count(testing.db, go, 0)

    def test_many_to_one(self):
        Company, Programmer, Manager, GolfSwing, Language = self.classes(
            "Company", "Programmer", "Manager", "GolfSwing", "Language"
        )
        sess = Session()
        company = (
            sess.query(Company)
            .filter(Company.id == 2)
            .options(
                selectinload(Company.employees.of_type(Manager)).selectinload(
                    Manager.golf_swing
                )
            )
            .one()
        )

        # NOTE: we *MUST* do a SQL compare on this one because the adaption
        # is very sensitive
        def go():
            eq_(company.employees[0].golf_swing.name, "clubs")

        self.assert_sql_count(testing.db, go, 0)

    def test_both(self):
        Company, Programmer, Manager, GolfSwing, Language = self.classes(
            "Company", "Programmer", "Manager", "GolfSwing", "Language"
        )
        sess = Session()
        rows = (
            sess.query(Company)
            .options(
                selectinload(Company.employees.of_type(Manager)).selectinload(
                    Manager.golf_swing
                ),
                defaultload(
                    Company.employees.of_type(Programmer)
                ).selectinload(Programmer.languages),
            )
            .order_by(Company.id)
            .all()
        )

        def go():
            eq_(rows[0].employees[0].languages[0].name, "Python")
            eq_(rows[1].employees[0].golf_swing.name, "clubs")

        self.assert_sql_count(testing.db, go, 0)


class TupleTest(fixtures.DeclarativeMappedTest):
    __requires__ = ("tuple_in",)

    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class A(fixtures.ComparableEntity, Base):
            __tablename__ = "a"
            id1 = Column(Integer, primary_key=True)
            id2 = Column(Integer, primary_key=True)

            bs = relationship("B", order_by="B.id", back_populates="a")

        class B(fixtures.ComparableEntity, Base):
            __tablename__ = "b"
            id = Column(Integer, primary_key=True)
            a_id1 = Column()
            a_id2 = Column()

            a = relationship("A", back_populates="bs")

            __table_args__ = (
                ForeignKeyConstraint(["a_id1", "a_id2"], ["a.id1", "a.id2"]),
            )

    @classmethod
    def insert_data(cls):
        A, B = cls.classes("A", "B")

        session = Session()
        session.add_all(
            [
                A(id1=i, id2=i + 2, bs=[B(id=(i * 6) + j) for j in range(6)])
                for i in range(1, 20)
            ]
        )
        session.commit()

    def test_load_o2m(self):
        A, B = self.classes("A", "B")

        session = Session()

        def go():
            q = (
                session.query(A)
                .options(selectinload(A.bs))
                .order_by(A.id1, A.id2)
            )
            return q.all()

        result = self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT a.id1 AS a_id1, a.id2 AS a_id2 "
                "FROM a ORDER BY a.id1, a.id2",
                {},
            ),
            CompiledSQL(
                "SELECT b.a_id1 AS b_a_id1, b.a_id2 AS b_a_id2, b.id AS b_id "
                "FROM b WHERE (b.a_id1, b.a_id2) IN "
                "([EXPANDING_primary_keys]) ORDER BY b.a_id1, b.a_id2, b.id",
                [{"primary_keys": [(i, i + 2) for i in range(1, 20)]}],
            ),
        )
        eq_(
            result,
            [
                A(id1=i, id2=i + 2, bs=[B(id=(i * 6) + j) for j in range(6)])
                for i in range(1, 20)
            ],
        )

    def test_load_m2o(self):
        A, B = self.classes("A", "B")

        session = Session()

        def go():
            q = session.query(B).options(selectinload(B.a)).order_by(B.id)
            return q.all()

        result = self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT b.id AS b_id, b.a_id1 AS b_a_id1, b.a_id2 AS b_a_id2 "
                "FROM b ORDER BY b.id",
                {},
            ),
            CompiledSQL(
                "SELECT a.id1 AS a_id1, a.id2 AS a_id2 FROM a "
                "WHERE (a.id1, a.id2) IN ([EXPANDING_primary_keys])",
                [{"primary_keys": [(i, i + 2) for i in range(1, 20)]}],
            ),
        )
        as_ = [A(id1=i, id2=i + 2) for i in range(1, 20)]

        eq_(
            result,
            [
                B(id=(i * 6) + j, a=as_[i - 1])
                for i in range(1, 20)
                for j in range(6)
            ],
        )


class ChunkingTest(fixtures.DeclarativeMappedTest):
    """test IN chunking.

    the length of IN has a limit on at least some databases.
    On Oracle it's 1000.  In any case, you don't want a SQL statement with
    500K entries in an IN, so larger results need to chunk.

    """

    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class A(fixtures.ComparableEntity, Base):
            __tablename__ = "a"
            id = Column(Integer, primary_key=True)
            bs = relationship("B", order_by="B.id", back_populates="a")

        class B(fixtures.ComparableEntity, Base):
            __tablename__ = "b"
            id = Column(Integer, primary_key=True)
            a_id = Column(ForeignKey("a.id"))
            a = relationship("A", back_populates="bs")

    @classmethod
    def insert_data(cls):
        A, B = cls.classes("A", "B")

        session = Session()
        session.add_all(
            [
                A(id=i, bs=[B(id=(i * 6) + j) for j in range(1, 6)])
                for i in range(1, 101)
            ]
        )
        session.commit()

    def test_odd_number_chunks(self):
        A, B = self.classes("A", "B")

        session = Session()

        def go():
            with mock.patch(
                "sqlalchemy.orm.strategies.SelectInLoader._chunksize", 47
            ):
                q = session.query(A).options(selectinload(A.bs)).order_by(A.id)

                for a in q:
                    a.bs

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL("SELECT a.id AS a_id FROM a ORDER BY a.id", {}),
            CompiledSQL(
                "SELECT b.a_id AS b_a_id, b.id AS b_id "
                "FROM b WHERE b.a_id IN "
                "([EXPANDING_primary_keys]) ORDER BY b.a_id, b.id",
                {"primary_keys": list(range(1, 48))},
            ),
            CompiledSQL(
                "SELECT b.a_id AS b_a_id, b.id AS b_id "
                "FROM b WHERE b.a_id IN "
                "([EXPANDING_primary_keys]) ORDER BY b.a_id, b.id",
                {"primary_keys": list(range(48, 95))},
            ),
            CompiledSQL(
                "SELECT b.a_id AS b_a_id, b.id AS b_id "
                "FROM b WHERE b.a_id IN "
                "([EXPANDING_primary_keys]) ORDER BY b.a_id, b.id",
                {"primary_keys": list(range(95, 101))},
            ),
        )

    @testing.requires.independent_cursors
    def test_yield_per(self):
        # the docs make a lot of guarantees about yield_per
        # so test that it works
        A, B = self.classes("A", "B")

        import random

        session = Session()

        yield_per = random.randint(8, 105)
        offset = random.randint(0, 19)
        total_rows = 100 - offset
        total_expected_statements = (
            1
            + int(total_rows / yield_per)
            + (1 if total_rows % yield_per else 0)
        )

        def go():
            for a in (
                session.query(A)
                .yield_per(yield_per)
                .offset(offset)
                .options(selectinload(A.bs))
            ):

                # this part fails with joined eager loading
                # (if you enable joined eager w/ yield_per)
                eq_(a.bs, [B(id=(a.id * 6) + j) for j in range(1, 6)])

        # this part fails with subquery eager loading
        # (if you enable subquery eager w/ yield_per)
        self.assert_sql_count(testing.db, go, total_expected_statements)

    def test_dont_emit_for_redundant_m2o(self):
        A, B = self.classes("A", "B")

        session = Session()

        def go():
            with mock.patch(
                "sqlalchemy.orm.strategies.SelectInLoader._chunksize", 47
            ):
                q = session.query(B).options(selectinload(B.a)).order_by(B.id)

                for b in q:
                    b.a

        self.assert_sql_execution(
            testing.db,
            go,
            CompiledSQL(
                "SELECT b.id AS b_id, b.a_id AS b_a_id FROM b ORDER BY b.id",
                {},
            ),
            # chunk size is 47.  so first chunk are a 1->47...
            CompiledSQL(
                "SELECT a.id AS a_id FROM a WHERE a.id IN "
                "([EXPANDING_primary_keys])",
                {"primary_keys": list(range(1, 48))},
            ),
            # second chunk is a 48-94
            CompiledSQL(
                "SELECT a.id AS a_id FROM a WHERE a.id IN "
                "([EXPANDING_primary_keys])",
                {"primary_keys": list(range(48, 95))},
            ),
            # third and final chunk 95-100.
            CompiledSQL(
                "SELECT a.id AS a_id FROM a WHERE a.id IN "
                "([EXPANDING_primary_keys])",
                {"primary_keys": list(range(95, 101))},
            ),
        )


class SubRelationFromJoinedSubclassMultiLevelTest(_Polymorphic):
    @classmethod
    def define_tables(cls, metadata):
        Table(
            "companies",
            metadata,
            Column(
                "company_id",
                Integer,
                primary_key=True,
                test_needs_autoincrement=True,
            ),
            Column("name", String(50)),
        )

        Table(
            "people",
            metadata,
            Column(
                "person_id",
                Integer,
                primary_key=True,
                test_needs_autoincrement=True,
            ),
            Column("company_id", ForeignKey("companies.company_id")),
            Column("name", String(50)),
            Column("type", String(30)),
        )

        Table(
            "engineers",
            metadata,
            Column(
                "engineer_id", ForeignKey("people.person_id"), primary_key=True
            ),
            Column("primary_language", String(50)),
        )

        Table(
            "machines",
            metadata,
            Column(
                "machine_id",
                Integer,
                primary_key=True,
                test_needs_autoincrement=True,
            ),
            Column("name", String(50)),
            Column("engineer_id", ForeignKey("engineers.engineer_id")),
            Column(
                "machine_type_id", ForeignKey("machine_type.machine_type_id")
            ),
        )

        Table(
            "machine_type",
            metadata,
            Column(
                "machine_type_id",
                Integer,
                primary_key=True,
                test_needs_autoincrement=True,
            ),
            Column("name", String(50)),
        )

    @classmethod
    def setup_mappers(cls):
        companies = cls.tables.companies
        people = cls.tables.people
        engineers = cls.tables.engineers
        machines = cls.tables.machines
        machine_type = cls.tables.machine_type

        mapper(
            Company,
            companies,
            properties={
                "employees": relationship(Person, order_by=people.c.person_id)
            },
        )
        mapper(
            Person,
            people,
            polymorphic_on=people.c.type,
            polymorphic_identity="person",
            with_polymorphic="*",
        )

        mapper(
            Engineer,
            engineers,
            inherits=Person,
            polymorphic_identity="engineer",
            properties={
                "machines": relationship(
                    Machine, order_by=machines.c.machine_id
                )
            },
        )

        mapper(
            Machine, machines, properties={"type": relationship(MachineType)}
        )
        mapper(MachineType, machine_type)

    @classmethod
    def insert_data(cls):
        c1 = cls._fixture()
        sess = create_session()
        sess.add(c1)
        sess.flush()

    @classmethod
    def _fixture(cls):
        mt1 = MachineType(name="mt1")
        mt2 = MachineType(name="mt2")
        return Company(
            employees=[
                Engineer(
                    name="e1",
                    machines=[
                        Machine(name="m1", type=mt1),
                        Machine(name="m2", type=mt2),
                    ],
                ),
                Engineer(
                    name="e2",
                    machines=[
                        Machine(name="m3", type=mt1),
                        Machine(name="m4", type=mt1),
                    ],
                ),
            ]
        )

    def test_chained_selectin_subclass(self):
        s = Session()
        q = s.query(Company).options(
            selectinload(Company.employees.of_type(Engineer))
            .selectinload(Engineer.machines)
            .selectinload(Machine.type)
        )

        def go():
            eq_(q.all(), [self._fixture()])

        self.assert_sql_count(testing.db, go, 4)


class SelfReferentialTest(fixtures.MappedTest):
    @classmethod
    def define_tables(cls, metadata):
        Table(
            "nodes",
            metadata,
            Column(
                "id", Integer, primary_key=True, test_needs_autoincrement=True
            ),
            Column("parent_id", Integer, ForeignKey("nodes.id")),
            Column("data", String(30)),
        )

    def test_basic(self):
        nodes = self.tables.nodes

        class Node(fixtures.ComparableEntity):
            def append(self, node):
                self.children.append(node)

        mapper(
            Node,
            nodes,
            properties={
                "children": relationship(
                    Node, lazy="selectin", join_depth=3, order_by=nodes.c.id
                )
            },
        )
        sess = create_session()
        n1 = Node(data="n1")
        n1.append(Node(data="n11"))
        n1.append(Node(data="n12"))
        n1.append(Node(data="n13"))
        n1.children[1].append(Node(data="n121"))
        n1.children[1].append(Node(data="n122"))
        n1.children[1].append(Node(data="n123"))
        n2 = Node(data="n2")
        n2.append(Node(data="n21"))
        n2.children[0].append(Node(data="n211"))
        n2.children[0].append(Node(data="n212"))

        sess.add(n1)
        sess.add(n2)
        sess.flush()
        sess.expunge_all()

        def go():
            d = (
                sess.query(Node)
                .filter(Node.data.in_(["n1", "n2"]))
                .order_by(Node.data)
                .all()
            )
            eq_(
                [
                    Node(
                        data="n1",
                        children=[
                            Node(data="n11"),
                            Node(
                                data="n12",
                                children=[
                                    Node(data="n121"),
                                    Node(data="n122"),
                                    Node(data="n123"),
                                ],
                            ),
                            Node(data="n13"),
                        ],
                    ),
                    Node(
                        data="n2",
                        children=[
                            Node(
                                data="n21",
                                children=[
                                    Node(data="n211"),
                                    Node(data="n212"),
                                ],
                            )
                        ],
                    ),
                ],
                d,
            )

        self.assert_sql_count(testing.db, go, 4)

    def test_lazy_fallback_doesnt_affect_eager(self):
        nodes = self.tables.nodes

        class Node(fixtures.ComparableEntity):
            def append(self, node):
                self.children.append(node)

        mapper(
            Node,
            nodes,
            properties={
                "children": relationship(
                    Node, lazy="selectin", join_depth=1, order_by=nodes.c.id
                )
            },
        )
        sess = create_session()
        n1 = Node(data="n1")
        n1.append(Node(data="n11"))
        n1.append(Node(data="n12"))
        n1.append(Node(data="n13"))
        n1.children[0].append(Node(data="n111"))
        n1.children[0].append(Node(data="n112"))
        n1.children[1].append(Node(data="n121"))
        n1.children[1].append(Node(data="n122"))
        n1.children[1].append(Node(data="n123"))
        sess.add(n1)
        sess.flush()
        sess.expunge_all()

        def go():
            allnodes = sess.query(Node).order_by(Node.data).all()

            n11 = allnodes[1]
            eq_(n11.data, "n11")
            eq_([Node(data="n111"), Node(data="n112")], list(n11.children))

            n12 = allnodes[4]
            eq_(n12.data, "n12")
            eq_(
                [Node(data="n121"), Node(data="n122"), Node(data="n123")],
                list(n12.children),
            )

        self.assert_sql_count(testing.db, go, 2)

    def test_with_deferred(self):
        nodes = self.tables.nodes

        class Node(fixtures.ComparableEntity):
            def append(self, node):
                self.children.append(node)

        mapper(
            Node,
            nodes,
            properties={
                "children": relationship(
                    Node, lazy="selectin", join_depth=3, order_by=nodes.c.id
                ),
                "data": deferred(nodes.c.data),
            },
        )
        sess = create_session()
        n1 = Node(data="n1")
        n1.append(Node(data="n11"))
        n1.append(Node(data="n12"))
        sess.add(n1)
        sess.flush()
        sess.expunge_all()

        def go():
            eq_(
                Node(data="n1", children=[Node(data="n11"), Node(data="n12")]),
                sess.query(Node).order_by(Node.id).first(),
            )

        self.assert_sql_count(testing.db, go, 6)

        sess.expunge_all()

        def go():
            eq_(
                Node(data="n1", children=[Node(data="n11"), Node(data="n12")]),
                sess.query(Node)
                .options(undefer("data"))
                .order_by(Node.id)
                .first(),
            )

        self.assert_sql_count(testing.db, go, 5)

        sess.expunge_all()

        def go():
            eq_(
                Node(data="n1", children=[Node(data="n11"), Node(data="n12")]),
                sess.query(Node)
                .options(undefer("data"), undefer("children.data"))
                .first(),
            )

        self.assert_sql_count(testing.db, go, 3)

    def test_options(self):
        nodes = self.tables.nodes

        class Node(fixtures.ComparableEntity):
            def append(self, node):
                self.children.append(node)

        mapper(
            Node,
            nodes,
            properties={"children": relationship(Node, order_by=nodes.c.id)},
        )
        sess = create_session()
        n1 = Node(data="n1")
        n1.append(Node(data="n11"))
        n1.append(Node(data="n12"))
        n1.append(Node(data="n13"))
        n1.children[1].append(Node(data="n121"))
        n1.children[1].append(Node(data="n122"))
        n1.children[1].append(Node(data="n123"))
        sess.add(n1)
        sess.flush()
        sess.expunge_all()

        def go():
            d = (
                sess.query(Node)
                .filter_by(data="n1")
                .order_by(Node.id)
                .options(selectinload("children").selectinload("children"))
                .first()
            )
            eq_(
                Node(
                    data="n1",
                    children=[
                        Node(data="n11"),
                        Node(
                            data="n12",
                            children=[
                                Node(data="n121"),
                                Node(data="n122"),
                                Node(data="n123"),
                            ],
                        ),
                        Node(data="n13"),
                    ],
                ),
                d,
            )

        self.assert_sql_count(testing.db, go, 3)

    def test_no_depth(self):
        """no join depth is set, so no eager loading occurs."""

        nodes = self.tables.nodes

        class Node(fixtures.ComparableEntity):
            def append(self, node):
                self.children.append(node)

        mapper(
            Node,
            nodes,
            properties={"children": relationship(Node, lazy="selectin")},
        )
        sess = create_session()
        n1 = Node(data="n1")
        n1.append(Node(data="n11"))
        n1.append(Node(data="n12"))
        n1.append(Node(data="n13"))
        n1.children[1].append(Node(data="n121"))
        n1.children[1].append(Node(data="n122"))
        n1.children[1].append(Node(data="n123"))
        n2 = Node(data="n2")
        n2.append(Node(data="n21"))
        sess.add(n1)
        sess.add(n2)
        sess.flush()
        sess.expunge_all()

        def go():
            d = (
                sess.query(Node)
                .filter(Node.data.in_(["n1", "n2"]))
                .order_by(Node.data)
                .all()
            )
            eq_(
                [
                    Node(
                        data="n1",
                        children=[
                            Node(data="n11"),
                            Node(
                                data="n12",
                                children=[
                                    Node(data="n121"),
                                    Node(data="n122"),
                                    Node(data="n123"),
                                ],
                            ),
                            Node(data="n13"),
                        ],
                    ),
                    Node(data="n2", children=[Node(data="n21")]),
                ],
                d,
            )

        self.assert_sql_count(testing.db, go, 4)


class SelfRefInheritanceAliasedTest(
    fixtures.DeclarativeMappedTest, testing.AssertsCompiledSQL
):
    __dialect__ = "default"

    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class Foo(fixtures.ComparableEntity, Base):
            __tablename__ = "foo"
            id = Column(Integer, primary_key=True)
            type = Column(String(50))

            foo_id = Column(Integer, ForeignKey("foo.id"))
            foo = relationship(
                lambda: Foo, foreign_keys=foo_id, remote_side=id
            )

            __mapper_args__ = {
                "polymorphic_on": type,
                "polymorphic_identity": "foo",
            }

        class Bar(Foo):
            __mapper_args__ = {"polymorphic_identity": "bar"}

    @classmethod
    def insert_data(cls):
        Foo, Bar = cls.classes("Foo", "Bar")

        session = Session()
        target = Bar(id=1)
        b1 = Bar(id=2, foo=Foo(id=3, foo=target))
        session.add(b1)
        session.commit()

    def test_twolevel_selectin_w_polymorphic(self):
        Foo, Bar = self.classes("Foo", "Bar")

        r = with_polymorphic(Foo, "*", aliased=True)
        attr1 = Foo.foo.of_type(r)
        attr2 = r.foo

        s = Session()
        q = (
            s.query(Foo)
            .filter(Foo.id == 2)
            .options(selectinload(attr1).selectinload(attr2))
        )
        results = self.assert_sql_execution(
            testing.db,
            q.all,
            CompiledSQL(
                "SELECT foo.id AS foo_id_1, foo.type AS foo_type, "
                "foo.foo_id AS foo_foo_id FROM foo WHERE foo.id = :id_1",
                [{"id_1": 2}],
            ),
            CompiledSQL(
                "SELECT foo_1.id AS foo_1_id, "
                "foo_1.type AS foo_1_type, foo_1.foo_id AS foo_1_foo_id "
                "FROM foo AS foo_1 "
                "WHERE foo_1.id IN ([EXPANDING_primary_keys])",
                {"primary_keys": [3]},
            ),
            CompiledSQL(
                "SELECT foo_1.id AS foo_1_id, "
                "foo_1.type AS foo_1_type, foo_1.foo_id AS foo_1_foo_id "
                "FROM foo AS foo_1 "
                "WHERE foo_1.id IN ([EXPANDING_primary_keys])",
                {"primary_keys": [1]},
            ),
        )
        eq_(results, [Bar(id=2, foo=Foo(id=3, foo=Bar(id=1)))])


class TestExistingRowPopulation(fixtures.DeclarativeMappedTest):
    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class A(Base):
            __tablename__ = "a"

            id = Column(Integer, primary_key=True)
            b_id = Column(ForeignKey("b.id"))
            a2_id = Column(ForeignKey("a2.id"))
            a2 = relationship("A2")
            b = relationship("B")

        class A2(Base):
            __tablename__ = "a2"

            id = Column(Integer, primary_key=True)
            b_id = Column(ForeignKey("b.id"))
            b = relationship("B")

        class B(Base):
            __tablename__ = "b"

            id = Column(Integer, primary_key=True)

            c1_m2o_id = Column(ForeignKey("c1_m2o.id"))
            c2_m2o_id = Column(ForeignKey("c2_m2o.id"))

            c1_o2m = relationship("C1o2m")
            c2_o2m = relationship("C2o2m")
            c1_m2o = relationship("C1m2o")
            c2_m2o = relationship("C2m2o")

        class C1o2m(Base):
            __tablename__ = "c1_o2m"

            id = Column(Integer, primary_key=True)
            b_id = Column(ForeignKey("b.id"))

        class C2o2m(Base):
            __tablename__ = "c2_o2m"

            id = Column(Integer, primary_key=True)
            b_id = Column(ForeignKey("b.id"))

        class C1m2o(Base):
            __tablename__ = "c1_m2o"

            id = Column(Integer, primary_key=True)

        class C2m2o(Base):
            __tablename__ = "c2_m2o"

            id = Column(Integer, primary_key=True)

    @classmethod
    def insert_data(cls):
        A, A2, B, C1o2m, C2o2m, C1m2o, C2m2o = cls.classes(
            "A", "A2", "B", "C1o2m", "C2o2m", "C1m2o", "C2m2o"
        )

        s = Session()

        b = B(
            c1_o2m=[C1o2m()], c2_o2m=[C2o2m()], c1_m2o=C1m2o(), c2_m2o=C2m2o()
        )

        s.add(A(b=b, a2=A2(b=b)))
        s.commit()

    def test_o2m(self):
        A, A2, B, C1o2m, C2o2m = self.classes("A", "A2", "B", "C1o2m", "C2o2m")

        s = Session()

        # A -J-> B -L-> C1
        # A -J-> B -S-> C2

        # A -J-> A2 -J-> B -S-> C1
        # A -J-> A2 -J-> B -L-> C2

        q = s.query(A).options(
            joinedload(A.b).selectinload(B.c2_o2m),
            joinedload(A.a2).joinedload(A2.b).selectinload(B.c1_o2m),
        )

        a1 = q.all()[0]

        is_true("c1_o2m" in a1.b.__dict__)
        is_true("c2_o2m" in a1.b.__dict__)

    def test_m2o(self):
        A, A2, B, C1m2o, C2m2o = self.classes("A", "A2", "B", "C1m2o", "C2m2o")

        s = Session()

        # A -J-> B -L-> C1
        # A -J-> B -S-> C2

        # A -J-> A2 -J-> B -S-> C1
        # A -J-> A2 -J-> B -L-> C2

        q = s.query(A).options(
            joinedload(A.b).selectinload(B.c2_m2o),
            joinedload(A.a2).joinedload(A2.b).selectinload(B.c1_m2o),
        )

        a1 = q.all()[0]
        is_true("c1_m2o" in a1.b.__dict__)
        is_true("c2_m2o" in a1.b.__dict__)


class SingleInhSubclassTest(
    fixtures.DeclarativeMappedTest, testing.AssertsExecutionResults
):
    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class User(Base):
            __tablename__ = "user"

            id = Column(Integer, primary_key=True)
            type = Column(String(10))

            __mapper_args__ = {"polymorphic_on": type}

        class EmployerUser(User):
            roles = relationship("Role", lazy="selectin")
            __mapper_args__ = {"polymorphic_identity": "employer"}

        class Role(Base):
            __tablename__ = "role"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("user.id"))

    @classmethod
    def insert_data(cls):
        EmployerUser, Role = cls.classes("EmployerUser", "Role")

        s = Session()
        s.add(EmployerUser(roles=[Role(), Role(), Role()]))
        s.commit()

    def test_load(self):
        EmployerUser, = self.classes("EmployerUser")
        s = Session()

        q = s.query(EmployerUser)

        self.assert_sql_execution(
            testing.db,
            q.all,
            CompiledSQL(
                'SELECT "user".id AS user_id, "user".type AS user_type '
                'FROM "user" WHERE "user".type IN (:type_1)',
                {"type_1": "employer"},
            ),
            CompiledSQL(
                "SELECT role.user_id AS role_user_id, role.id AS role_id "
                "FROM role WHERE role.user_id "
                "IN ([EXPANDING_primary_keys]) ORDER BY role.user_id",
                {"primary_keys": [1]},
            ),
        )


class M2OWDegradeTest(
    fixtures.DeclarativeMappedTest, testing.AssertsExecutionResults
):
    @classmethod
    def setup_classes(cls):
        Base = cls.DeclarativeBasic

        class A(fixtures.ComparableEntity, Base):
            __tablename__ = "a"
            id = Column(Integer, primary_key=True)
            b_id = Column(ForeignKey("b.id"))
            b = relationship("B")
            q = Column(Integer)

        class B(fixtures.ComparableEntity, Base):
            __tablename__ = "b"
            id = Column(Integer, primary_key=True)
            x = Column(Integer)
            y = Column(Integer)

    @classmethod
    def insert_data(cls):
        A, B = cls.classes("A", "B")

        s = Session()
        b1, b2 = B(id=1, x=5, y=9), B(id=2, x=10, y=8)
        s.add_all(
            [
                A(id=1, b=b1),
                A(id=2, b=b2),
                A(id=3, b=b2),
                A(id=4, b=None),
                A(id=5, b=b1),
            ]
        )
        s.commit()

    def test_use_join_parent_criteria(self):
        A, B = self.classes("A", "B")
        s = Session()
        q = (
            s.query(A)
            .filter(A.id.in_([1, 3]))
            .options(selectinload(A.b))
            .order_by(A.id)
        )
        results = self.assert_sql_execution(
            testing.db,
            q.all,
            CompiledSQL(
                "SELECT a.id AS a_id, a.b_id AS a_b_id, a.q AS a_q "
                "FROM a WHERE a.id IN (:id_1, :id_2) ORDER BY a.id",
                [{"id_1": 1, "id_2": 3}],
            ),
            CompiledSQL(
                "SELECT b.id AS b_id, b.x AS b_x, b.y AS b_y "
                "FROM b WHERE b.id IN ([EXPANDING_primary_keys])",
                [{"primary_keys": [1, 2]}],
            ),
        )

        eq_(
            results,
            [A(id=1, b=B(id=1, x=5, y=9)), A(id=3, b=B(id=2, x=10, y=8))],
        )

    def test_use_join_parent_criteria_degrade_on_defer(self):
        A, B = self.classes("A", "B")
        s = Session()
        q = (
            s.query(A)
            .filter(A.id.in_([1, 3]))
            .options(defer(A.b_id), selectinload(A.b))
            .order_by(A.id)
        )
        results = self.assert_sql_execution(
            testing.db,
            q.all,
            CompiledSQL(
                "SELECT a.id AS a_id, a.q AS a_q "
                "FROM a WHERE a.id IN (:id_1, :id_2) ORDER BY a.id",
                [{"id_1": 1, "id_2": 3}],
            ),
            # in the very unlikely case that the the FK col on parent is
            # deferred, we degrade to the JOIN version so that we don't need to
            # emit either for each parent object individually, or as a second
            # query for them.
            CompiledSQL(
                "SELECT a_1.id AS a_1_id, b.id AS b_id, b.x AS b_x, "
                "b.y AS b_y "
                "FROM a AS a_1 JOIN b ON b.id = a_1.b_id "
                "WHERE a_1.id IN ([EXPANDING_primary_keys]) ORDER BY a_1.id",
                [{"primary_keys": [1, 3]}],
            ),
        )

        eq_(
            results,
            [A(id=1, b=B(id=1, x=5, y=9)), A(id=3, b=B(id=2, x=10, y=8))],
        )

    def test_use_join(self):
        A, B = self.classes("A", "B")
        s = Session()
        q = s.query(A).options(selectinload(A.b)).order_by(A.id)
        results = self.assert_sql_execution(
            testing.db,
            q.all,
            CompiledSQL(
                "SELECT a.id AS a_id, a.b_id AS a_b_id, a.q AS a_q "
                "FROM a ORDER BY a.id",
                [{}],
            ),
            CompiledSQL(
                "SELECT b.id AS b_id, b.x AS b_x, b.y AS b_y "
                "FROM b WHERE b.id IN ([EXPANDING_primary_keys])",
                [{"primary_keys": [1, 2]}],
            ),
        )

        b1, b2 = B(id=1, x=5, y=9), B(id=2, x=10, y=8)
        eq_(
            results,
            [
                A(id=1, b=b1),
                A(id=2, b=b2),
                A(id=3, b=b2),
                A(id=4, b=None),
                A(id=5, b=b1),
            ],
        )

    def test_use_join_parent_degrade_on_defer(self):
        A, B = self.classes("A", "B")
        s = Session()
        q = s.query(A).options(defer(A.b_id), selectinload(A.b)).order_by(A.id)
        results = self.assert_sql_execution(
            testing.db,
            q.all,
            CompiledSQL(
                "SELECT a.id AS a_id, a.q AS a_q " "FROM a ORDER BY a.id", [{}]
            ),
            # in the very unlikely case that the the FK col on parent is
            # deferred, we degrade to the JOIN version so that we don't need to
            # emit either for each parent object individually, or as a second
            # query for them.
            CompiledSQL(
                "SELECT a_1.id AS a_1_id, b.id AS b_id, b.x AS b_x, "
                "b.y AS b_y "
                "FROM a AS a_1 JOIN b ON b.id = a_1.b_id "
                "WHERE a_1.id IN ([EXPANDING_primary_keys]) ORDER BY a_1.id",
                [{"primary_keys": [1, 2, 3, 4, 5]}],
            ),
        )

        b1, b2 = B(id=1, x=5, y=9), B(id=2, x=10, y=8)
        eq_(
            results,
            [
                A(id=1, b=b1),
                A(id=2, b=b2),
                A(id=3, b=b2),
                A(id=4, b=None),
                A(id=5, b=b1),
            ],
        )
