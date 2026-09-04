# Generated migration for VisitRecording model and Urgent priority tier

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0005_leadentry_smslog_triageescalationlog_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointments',
            name='priority_tier',
            field=models.CharField(
                choices=[
                    ('Routine', 'Routine'),
                    ('Waitlist', 'Waitlist'),
                    ('Priority-Revisit', 'Priority-Revisit'),
                    ('Urgent', 'Urgent'),
                ],
                default='Routine',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='VisitRecording',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recorded_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('transcript', models.TextField(help_text='Full conversation or visit transcript')),
                ('soap_summary', models.TextField(blank=True, default='', help_text='Structured clinical summary')),
                ('priority_assessed', models.CharField(default='Routine', max_length=20)),
                ('risk_score', models.IntegerField(default=0)),
                ('source', models.CharField(
                    choices=[
                        ('ai_booking', 'AI Booking Call'),
                        ('consultation', 'Live Consultation'),
                        ('ambient_scribe', 'Ambient Scribe'),
                    ],
                    default='consultation',
                    max_length=30,
                )),
                ('duration_seconds', models.IntegerField(blank=True, default=0)),
                ('appointment', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='visit_recordings', to='doctor.appointments',
                )),
                ('doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='visit_recordings', to='doctor.doctorprofile',
                )),
                ('patient', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='visit_recordings', to='doctor.patients',
                )),
            ],
            options={
                'ordering': ['-recorded_at'],
            },
        ),
    ]
