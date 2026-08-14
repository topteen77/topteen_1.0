# Migration to add skilllab_skilllabmcqquestion and skilllab_skilllabmcqanswer
# when they are missing (e.g. production had only skilllab_skilllabmcq before 0002 was faked)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('skilllab', '0013_add_course_progress_summary'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS skilllab_skilllabmcqquestion (
                id bigint NOT NULL AUTO_INCREMENT,
                created datetime(6) NOT NULL,
                modified datetime(6) NOT NULL,
                object_status smallint NOT NULL DEFAULT 1,
                question_number int unsigned NOT NULL DEFAULT 1,
                question_text longtext NOT NULL,
                `order` int unsigned NOT NULL DEFAULT 0,
                mcq_id bigint NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY skilllab_skilllabmcqq_mcq_id_question__uniq (mcq_id, question_number),
                KEY skilllab_skilllabmcqq_mcq_id_idx (mcq_id),
                CONSTRAINT skilllab_skilllabmcqq_mcq_id_fk FOREIGN KEY (mcq_id) REFERENCES skilllab_skilllabmcq (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            reverse_sql="DROP TABLE IF EXISTS skilllab_skilllabmcqquestion;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS skilllab_skilllabmcqanswer (
                id bigint NOT NULL AUTO_INCREMENT,
                created datetime(6) NOT NULL,
                modified datetime(6) NOT NULL,
                object_status smallint NOT NULL DEFAULT 1,
                answer_letter varchar(1) NOT NULL,
                answer_text longtext NOT NULL,
                is_correct tinyint(1) NOT NULL DEFAULT 0,
                `order` int unsigned NOT NULL DEFAULT 0,
                question_id bigint NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY skilllab_skilllabmcqa_question_id_answer__uniq (question_id, answer_letter),
                KEY skilllab_skilllabmcqa_question_id_idx (question_id),
                CONSTRAINT skilllab_skilllabmcqa_question_id_fk FOREIGN KEY (question_id) REFERENCES skilllab_skilllabmcqquestion (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            reverse_sql="DROP TABLE IF EXISTS skilllab_skilllabmcqanswer;",
        ),
    ]
