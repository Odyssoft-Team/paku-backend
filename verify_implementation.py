#!/usr/bin/env python3
"""
🔍 CHECKLIST DE VERIFICACIÓN - Distritos Hardcodeados

Este script verifica que todos los cambios se implementaron correctamente.
Ejecutar antes de considerar la feature como completa.
"""

import os
import sys
from pathlib import Path


def check_file_exists(file_path: str, description: str) -> bool:
    """Verifica que un archivo existe."""
    exists = os.path.exists(file_path)
    status = "✅" if exists else "❌"
    print(f"{status} {description}")
    if not exists:
        print(f"   └─ Archivo no encontrado: {file_path}")
    return exists


def check_file_contains(file_path: str, search_text: str, description: str) -> bool:
    """Verifica que un archivo contiene cierto texto."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            contains = search_text in content
            status = "✅" if contains else "❌"
            print(f"{status} {description}")
            if not contains:
                print(f"   └─ No se encontró: '{search_text[:50]}...'")
            return contains
    except Exception as e:
        print(f"❌ {description}")
        print(f"   └─ Error: {e}")
        return False


def run_checklist():
    """Ejecuta el checklist completo."""
    
    print("\n" + "=" * 80)
    print("🔍 CHECKLIST DE VERIFICACIÓN - Distritos Hardcodeados")
    print("=" * 80)
    
    base_path = Path(__file__).parent
    all_checks = []
    
    # ========================================================================
    print("\n📁 SECCIÓN 1: Archivos Nuevos Creados")
    print("-" * 80)
    
    checks = [
        check_file_exists(
            str(base_path / "app/modules/geo/infra/districts_data.py"),
            "Archivo de datos hardcodeados (districts_data.py)"
        ),
        check_file_exists(
            str(base_path / "app/modules/geo/README.md"),
            "Documentación del módulo Geo (README.md)"
        ),
        check_file_exists(
            str(base_path / "test_districts_simple.py"),
            "Test simple sin dependencias (test_districts_simple.py)"
        ),
        check_file_exists(
            str(base_path / "CAMBIOS_DISTRITOS.md"),
            "Documentación de cambios (CAMBIOS_DISTRITOS.md)"
        ),
        check_file_exists(
            str(base_path / "API_EXAMPLES.md"),
            "Ejemplos de API (API_EXAMPLES.md)"
        ),
        check_file_exists(
            str(base_path / "RESUMEN_EJECUTIVO.md"),
            "Resumen ejecutivo (RESUMEN_EJECUTIVO.md)"
        ),
    ]
    all_checks.extend(checks)
    
    # ========================================================================
    print("\n🔧 SECCIÓN 2: Contenido de districts_data.py")
    print("-" * 80)
    
    districts_file = str(base_path / "app/modules/geo/infra/districts_data.py")
    checks = [
        check_file_contains(
            districts_file,
            "DISTRICTS_DATA",
            "Define array DISTRICTS_DATA"
        ),
        check_file_contains(
            districts_file,
            '"150104"',
            "Contiene distrito Barranco (150104)"
        ),
        check_file_contains(
            districts_file,
            '"150113"',
            "Contiene distrito Jesús María (150113)"
        ),
        check_file_contains(
            districts_file,
            '"150116"',
            "Contiene distrito Lince (150116)"
        ),
        check_file_contains(
            districts_file,
            "get_all_districts",
            "Define función get_all_districts()"
        ),
        check_file_contains(
            districts_file,
            "get_district_by_id",
            "Define función get_district_by_id()"
        ),
    ]
    all_checks.extend(checks)
    
    # ========================================================================
    print("\n🔧 SECCIÓN 3: Modificaciones en repository.py")
    print("-" * 80)
    
    repo_file = str(base_path / "app/modules/geo/infra/repository.py")
    checks = [
        check_file_contains(
            repo_file,
            "from app.modules.geo.infra.districts_data import",
            "Importa funciones de districts_data"
        ),
        check_file_contains(
            repo_file,
            "get_all_districts",
            "Usa get_all_districts() en lugar de query BD"
        ),
        check_file_contains(
            repo_file,
            "get_district_by_id",
            "Usa get_district_by_id() en lugar de query BD"
        ),
        check_file_contains(
            repo_file,
            "HARDCODED",
            "Documentación indica que usa hardcoded data"
        ),
    ]
    all_checks.extend(checks)
    
    # ========================================================================
    print("\n📚 SECCIÓN 4: Documentación Actualizada")
    print("-" * 80)
    
    checks = [
        check_file_contains(
            str(base_path / "README.md"),
            "Geo Module",
            "README principal menciona módulo Geo"
        ),
        check_file_contains(
            str(base_path / "app/modules/geo/README.md"),
            "Hardcoded Data",
            "README de Geo explica approach hardcoded"
        ),
        check_file_contains(
            str(base_path / "API_EXAMPLES.md"),
            "GET /geo/districts",
            "Ejemplos de API incluyen endpoints de distritos"
        ),
    ]
    all_checks.extend(checks)
    
    # ========================================================================
    print("\n🧪 SECCIÓN 5: Ejecutar Test Simple")
    print("-" * 80)
    
    test_file = str(base_path / "test_districts_simple.py")
    if os.path.exists(test_file):
        print("🚀 Ejecutando test_districts_simple.py...")
        print("-" * 80)
        
        import subprocess
        try:
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("✅ Test ejecutado exitosamente")
                all_checks.append(True)
                # Mostrar solo el resumen del test
                lines = result.stdout.split('\n')
                for line in lines:
                    if '✅' in line or 'Summary' in line or 'districts' in line.lower():
                        print(f"   {line}")
            else:
                print("❌ Test falló")
                print(result.stderr)
                all_checks.append(False)
        except subprocess.TimeoutExpired:
            print("❌ Test timeout (>10s)")
            all_checks.append(False)
        except Exception as e:
            print(f"❌ Error ejecutando test: {e}")
            all_checks.append(False)
    else:
        print("❌ Archivo de test no encontrado")
        all_checks.append(False)
    
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 RESULTADO FINAL")
    print("=" * 80)
    
    passed = sum(all_checks)
    total = len(all_checks)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\n✅ Checks pasados: {passed}/{total} ({percentage:.1f}%)")
    
    if percentage == 100:
        print("\n" + "🎉" * 40)
        print("\n   ✅ TODOS LOS CHECKS PASARON!")
        print("   🚀 La implementación está completa y lista para usar")
        print("\n" + "🎉" * 40)
        return 0
    elif percentage >= 80:
        print("\n⚠️  La mayoría de checks pasaron, pero hay algunos pendientes.")
        print("   Revisa los items marcados con ❌ arriba.")
        return 1
    else:
        print("\n❌ Muchos checks fallaron. Revisa la implementación.")
        return 1


if __name__ == "__main__":
    sys.exit(run_checklist())
