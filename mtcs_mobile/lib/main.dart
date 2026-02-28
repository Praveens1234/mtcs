import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/theme_provider.dart';
import 'package:mtcs_mobile/providers/system_state_provider.dart';
import 'package:mtcs_mobile/utils/router.dart';
import 'package:mtcs_mobile/utils/theme.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => SystemStateProvider()),
      ],
      child: const MtcsMobileApp(),
    ),
  );
}

class MtcsMobileApp extends StatelessWidget {
  const MtcsMobileApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Consumer<ThemeProvider>(
      builder: (context, themeProvider, child) {
        return MaterialApp.router(
          title: 'MTCS Mobile Engine',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: themeProvider.themeMode,
          routerConfig: appRouter,
          debugShowCheckedModeBanner: false,
        );
      },
    );
  }
}
