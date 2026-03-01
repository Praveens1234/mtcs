import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mtcs_mobile/screens/dashboard_screen.dart';
import 'package:mtcs_mobile/screens/accounts_screen.dart';
import 'package:mtcs_mobile/screens/quotes_screen.dart';
import 'package:mtcs_mobile/screens/history_screen.dart';
import 'package:mtcs_mobile/screens/settings_screen.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');
final GlobalKey<NavigatorState> _shellNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'shell');

final GoRouter appRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/dashboard',
  routes: [
    ShellRoute(
      navigatorKey: _shellNavigatorKey,
      builder: (BuildContext context, GoRouterState state, Widget child) {
        return ScaffoldWithNavBar(child: child);
      },
      routes: <RouteBase>[
        GoRoute(
          path: '/dashboard',
          builder: (BuildContext context, GoRouterState state) => const DashboardScreen(),
        ),
        GoRoute(
          path: '/quotes',
          builder: (BuildContext context, GoRouterState state) => const QuotesScreen(),
        ),
        GoRoute(
          path: '/accounts',
          builder: (BuildContext context, GoRouterState state) => const AccountsScreen(),
        ),
        GoRoute(
          path: '/history',
          builder: (BuildContext context, GoRouterState state) => const HistoryScreen(),
        ),
        GoRoute(
          path: '/settings',
          builder: (BuildContext context, GoRouterState state) => const SettingsScreen(),
        ),
      ],
    ),
  ],
);

class ScaffoldWithNavBar extends StatelessWidget {
  const ScaffoldWithNavBar({required this.child, Key? key}) : super(key: key);
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: BottomNavigationBar(
        items: const <BottomNavigationBarItem>[
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), activeIcon: Icon(Icons.dashboard), label: 'Dash'),
          BottomNavigationBarItem(icon: Icon(Icons.show_chart_outlined), activeIcon: Icon(Icons.show_chart), label: 'Quotes'),
          BottomNavigationBarItem(icon: Icon(Icons.account_balance_wallet_outlined), activeIcon: Icon(Icons.account_balance_wallet), label: 'Accounts'),
          BottomNavigationBarItem(icon: Icon(Icons.history_outlined), activeIcon: Icon(Icons.history), label: 'History'),
          BottomNavigationBarItem(icon: Icon(Icons.settings_outlined), activeIcon: Icon(Icons.settings), label: 'Settings'),
        ],
        currentIndex: _calculateSelectedIndex(context),
        onTap: (int idx) => _onItemTapped(idx, context),
      ),
    );
  }

  static int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.toString();
    if (location.startsWith('/dashboard')) return 0;
    if (location.startsWith('/quotes')) return 1;
    if (location.startsWith('/accounts')) return 2;
    if (location.startsWith('/history')) return 3;
    if (location.startsWith('/settings')) return 4;
    return 0;
  }

  void _onItemTapped(int index, BuildContext context) {
    switch (index) {
      case 0: GoRouter.of(context).go('/dashboard'); break;
      case 1: GoRouter.of(context).go('/quotes'); break;
      case 2: GoRouter.of(context).go('/accounts'); break;
      case 3: GoRouter.of(context).go('/history'); break;
      case 4: GoRouter.of(context).go('/settings'); break;
    }
  }
}
