#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rasch Model Implementation - R eRm kutubxonasi bilan
Item Response Theory (IRT) - Rasch modeliga asoslangan talaba baholash tizimi

Bu modul R tilining eRm kutubxonasini Python orqali ishlatadi (rpy2).
eRm - Extended Rasch Modeling - eng ishonchli Rasch model implementatsiyasi.

Rasch model formulasi: P(X=1|θ, β) = exp(θ - β) / (1 + exp(θ - β))
Bu yerda:
    θ (theta) - talabaning qobiliyati (ability / person parameter)
    β (beta) - savolning qiyinligi (difficulty / item parameter)
    
Standard ball formulasi: T = 50 + 10Z
Bu yerda:
    Z = (θ - μ) / σ
    μ - o'rtacha qiymat
    σ - standart tafovut
"""

import numpy as np
import logging
from scipy.stats import norm

logger = logging.getLogger(__name__)

# R va eRm kutubxonasini import qilish
_R_AVAILABLE = False
_ERM_AVAILABLE = False

try:
    import warnings
    warnings.filterwarnings('ignore', message='.*activate.*deprecated.*')
    
    import rpy2.robjects as ro
    from rpy2.robjects.packages import importr
    
    # pandas2ri ni xavfsiz yuklash (agar kerak bo'lsa)
    try:
        from rpy2.robjects import pandas2ri
        pandas2ri.activate()  # Warning chiqsa ham ishlaydi
    except:
        pass  # pandas2ri kerak emas bizga
    
    _R_AVAILABLE = True
    logger.info("✅ rpy2 kutubxonasi muvaffaqiyatli yuklandi")
except Exception as e:
    logger.warning(f"⚠️ rpy2 yuklanmadi: {str(e)[:100]}")
    logger.warning("Fallback JMLE algoritmi ishlatiladi")

if _R_AVAILABLE:
    try:
        # R base funksiyalarini yuklash
        base = importr('base')
        utils = importr('utils')
        
        # eRm kutubxonasini yuklash
        erm = importr('eRm')
        _ERM_AVAILABLE = True
        logger.info("✅ R eRm kutubxonasi muvaffaqiyatli yuklandi")
    except Exception as e:
        logger.warning(f"⚠️ R eRm kutubxonasi yuklanmadi: {e}")
        logger.warning("eRm o'rnatish uchun: install.packages('eRm')")
        logger.warning("Fallback algoritm ishlatiladi")


class RaschModel:
    """
    Rasch Model - R eRm kutubxonasi orqali IRT tahlili
    """
    
    def __init__(self):
        """Rasch model obyektini yaratish"""
        self.theta_estimates = None  # Talabalar qobiliyati
        self.beta_estimates = None   # Savollar qiyinligi
        self.se_theta = None         # Theta standart xatosi
        self.se_beta = None          # Beta standart xatosi
        self.fitted = False
        self.use_erm = _ERM_AVAILABLE
        
    def calculate_theta(self, correct_count, total_questions):
        """
        Talaba qobiliyatini (theta) hisoblash - oddiy usul (fallback)
        
        Args:
            correct_count: To'g'ri javoblar soni
            total_questions: Jami savollar soni
        
        Returns:
            float: Theta (qobiliyat) qiymati
        """
        if total_questions == 0:
            return 0.0
        
        # Foiz hisoblab logit transformatsiya qilish
        p = correct_count / total_questions
        
        # Logit transformation: logit(p) = ln(p / (1-p))
        if p == 1.0:
            return 3.0
        elif p == 0.0:
            return -3.0
        else:
            theta = np.log(p / (1 - p))
            theta = np.clip(theta, -3.0, 3.0)
            return float(theta)
    
    def fit(self, response_matrix):
        """
        Rasch modelini ma'lumotlarga moslashtirish (fitting)
        eRm kutubxonasi orqali yoki fallback algoritm
        
        Args:
            response_matrix: numpy array (n_students x n_items)
                            1 = to'g'ri javob, 0 = noto'g'ri javob
        
        Returns:
            bool: Muvaffaqiyatli fit bo'lsa True
        """
        try:
            n_students, n_items = response_matrix.shape
            
            if self.use_erm and _ERM_AVAILABLE:
                # eRm kutubxonasi orqali hisoblash
                logger.info("🔬 eRm kutubxonasi orqali Rasch model fitting...")
                return self._fit_with_erm(response_matrix)
            else:
                # Fallback: oddiy JMLE algoritmi
                logger.info("🔬 Fallback JMLE algoritmi orqali Rasch model fitting...")
                return self._fit_with_jmle(response_matrix)
                
        except Exception as e:
            logger.error(f"Rasch model fit xatosi: {e}")
            return False
    
    def _fit_with_erm(self, response_matrix):
        """eRm kutubxonasi orqali Rasch model fitting"""
        try:
            n_students, n_items = response_matrix.shape
            
            # Response matrix ni R ga o'tkazish
            # Har bir qatorni alohida yuborish (to'g'ri format uchun)
            response_list = []
            for i in range(n_students):
                for j in range(n_items):
                    response_list.append(int(response_matrix[i, j]))
            
            # R matrixni yaratish
            # matrix(data, nrow=n, ncol=m, byrow=TRUE)
            ro.r.assign('n_students', n_students)
            ro.r.assign('n_items', n_items)
            ro.r.assign('response_vec', ro.IntVector(response_list))
            ro.r('response_data <- matrix(response_vec, nrow=n_students, ncol=n_items, byrow=TRUE)')
            
            # eRm RM funksiyasini chaqirish (Rasch Model)
            # RM - eRm ning asosiy Rasch model funksiyasi
            result = ro.r('''
                # Rasch modelini fit qilish
                tryCatch({
                    # RM - Rasch modelini fit qilish
                    rasch_fit <- RM(response_data)
                    
                    # Item parametrlarini olish (beta - qiyinlik)
                    item_params <- as.numeric(coef(rasch_fit))
                    
                    # Person parametrlarini olish (theta - qobiliyat)
                    person_params <- person.parameter(rasch_fit)
                    
                    # Theta values ni olish
                    if (!is.null(person_params$thetapar)) {
                        theta_values <- as.numeric(person_params$thetapar$NAgroup1[, "Person Parameter"])
                        se_persons <- as.numeric(person_params$thetapar$NAgroup1[, "Error"])
                    } else {
                        theta_values <- NULL
                        se_persons <- NULL
                    }
                    
                    # Standart xatolar
                    se_items <- if (!is.null(rasch_fit$se.beta)) as.numeric(rasch_fit$se.beta) else NULL
                    
                    list(
                        item_params = item_params,
                        theta_values = theta_values,
                        se_items = se_items,
                        se_persons = se_persons,
                        success = TRUE
                    )
                }, error = function(e) {
                    list(success = FALSE, error = as.character(e$message))
                })
            ''')
            
            if result.rx2('success')[0]:
                # Item parametrlar (beta - qiyinlik)
                self.beta_estimates = np.array(result.rx2('item_params'))
                
                # Person parametrlar (theta - qobiliyat)
                theta_raw = np.array(result.rx2('theta_values'))
                
                # NaN/Inf qiymatlarni qayta ishlash (ekstrem holatlar uchun)
                theta_clean = []
                for i, theta in enumerate(theta_raw):
                    if np.isnan(theta) or np.isinf(theta):
                        # Ekstrem hol: barcha javoblar to'g'ri yoki xato
                        correct_count = int(np.sum(response_matrix[i, :]))
                        if correct_count == n_items:
                            theta_clean.append(3.0)  # Maksimal
                        elif correct_count == 0:
                            theta_clean.append(-3.0)  # Minimal
                        else:
                            theta_clean.append(0.0)  # Default
                    else:
                        theta_clean.append(float(theta))
                
                self.theta_estimates = np.array(theta_clean)
                
                # Standart xatolar
                try:
                    self.se_beta = np.array(result.rx2('se_items'))
                    self.se_theta = np.array(result.rx2('se_persons'))
                except:
                    logger.warning("Standart xatolarni olishda muammo")
                    self.se_beta = np.ones_like(self.beta_estimates) * 0.5
                    self.se_theta = np.ones_like(self.theta_estimates) * 0.5
                
                # Theta ni o'rtacha 0 ga sozlash (normalizatsiya)
                mean_theta = np.mean(self.theta_estimates)
                self.theta_estimates = self.theta_estimates - mean_theta
                
                self.fitted = True
                logger.info(f"✅ eRm orqali muvaffaqiyatli fit qilindi: {n_students} talaba, {n_items} savol")
                return True
            else:
                error_msg = result.rx2('error')[0] if 'error' in result.names else "Noma'lum xato"
                logger.error(f"eRm fit xatosi: {error_msg}")
                return self._fit_with_jmle(response_matrix)
                
        except Exception as e:
            logger.error(f"eRm fit xatosi: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback ga o'tish
            return self._fit_with_jmle(response_matrix)
    
    def _fit_with_jmle(self, response_matrix):
        """Fallback: JMLE (Joint Maximum Likelihood Estimation) algoritmi"""
        try:
            from scipy.optimize import minimize
            
            n_students, n_items = response_matrix.shape
            
            # Boshlang'ich qiymatlar
            theta = np.zeros(n_students)
            beta = np.zeros(n_items)
            
            max_iterations = 100
            tolerance = 1e-4
            
            for iteration in range(max_iterations):
                theta_old = theta.copy()
                beta_old = beta.copy()
                
                # Theta (talaba qobiliyati) ni yangilash
                for i in range(n_students):
                    observed = response_matrix[i, :]
                    if np.sum(observed) == 0 or np.sum(observed) == n_items:
                        continue
                    
                    def neg_log_likelihood(t):
                        p = 1 / (1 + np.exp(-(t - beta)))
                        ll = np.sum(observed * np.log(p + 1e-10) + 
                                   (1 - observed) * np.log(1 - p + 1e-10))
                        return -ll
                    
                    result = minimize(neg_log_likelihood, theta[i], method='BFGS')
                    theta[i] = result.x[0]
                
                # Beta (savol qiyinligi) ni yangilash
                for j in range(n_items):
                    observed = response_matrix[:, j]
                    if np.sum(observed) == 0 or np.sum(observed) == n_students:
                        continue
                    
                    def neg_log_likelihood(b):
                        p = 1 / (1 + np.exp(-(theta - b)))
                        ll = np.sum(observed * np.log(p + 1e-10) + 
                                   (1 - observed) * np.log(1 - p + 1e-10))
                        return -ll
                    
                    result = minimize(neg_log_likelihood, beta[j], method='BFGS')
                    beta[j] = result.x[0]
                
                # Konvergentsiya tekshiruvi
                theta_change = np.max(np.abs(theta - theta_old))
                beta_change = np.max(np.abs(beta - beta_old))
                
                if theta_change < tolerance and beta_change < tolerance:
                    logger.info(f"JMLE konvergentsiya qildi (iteration {iteration + 1})")
                    break
            
            # Theta ni o'rtacha 0 ga sozlash
            theta = theta - np.mean(theta)
            
            self.theta_estimates = theta
            self.beta_estimates = beta
            self.fitted = True
            
            logger.info(f"✅ JMLE orqali muvaffaqiyatli fit qilindi: {n_students} talaba, {n_items} savol")
            return True
            
        except Exception as e:
            logger.error(f"JMLE fit xatosi: {e}")
            return False
    
    def calculate_standard_score(self, theta, mean_theta, std_theta):
        """
        Theta ni standart ball (T-score) ga aylantirish
        Formula: T = 50 + 10Z
        Z = (θ - μ) / σ
        
        Args:
            theta: Talaba qobiliyati
            mean_theta: O'rtacha theta
            std_theta: Standart tafovut
        
        Returns:
            float: Standard ball (T-score)
        """
        if std_theta == 0:
            return 50.0
        
        # Z-score hisoblash
        z_score = (theta - mean_theta) / std_theta
        
        # T-score hisoblash (rasmda ko'rsatilgan formula)
        t_score = 50 + 10 * z_score
        
        # 0 dan 100 gacha chegaralash
        t_score = np.clip(t_score, 0, 100)
        
        return float(t_score)


def evaluate_with_rasch(response_matrix, user_ids=None):
    """
    Rasch modelini ishlatib talabalarni baholash va natijalarni standart shkala bo'yicha berish
    eRm kutubxonasi yoki JMLE algoritmi orqali
    
    Args:
        response_matrix: numpy array (n_students x n_items)
                        1 = to'g'ri javob, 0 = noto'g'ri javob
        user_ids: list, talabalar ID lari
    
    Returns:
        list: Har bir talaba uchun natijalar (dict)
        dict: Umumiy statistika
    """
    try:
        n_students, n_items = response_matrix.shape
        
        if user_ids is None:
            user_ids = [f"Student_{i+1}" for i in range(n_students)]
        
        # Rasch modelini yaratish va fit qilish
        rasch_model = RaschModel()
        success = rasch_model.fit(response_matrix)
        
        if not success or rasch_model.theta_estimates is None:
            logger.warning("Rasch model fit bo'lmadi, oddiy usuldan foydalanamiz")
            # Fallback: oddiy theta hisoblash
            results = []
            for i in range(n_students):
                correct_count = int(np.sum(response_matrix[i, :]))
                theta = rasch_model.calculate_theta(correct_count, n_items)
                
                results.append({
                    'user_id': user_ids[i],
                    'correct': correct_count,
                    'total': n_items,
                    'percentage': (correct_count / n_items * 100) if n_items > 0 else 0,
                    'theta': theta,
                    'rasch_score': theta,
                    't_score': 50.0,
                    'responses': response_matrix[i, :].tolist()
                })
            
            # O'rtacha theta va standart tafovut
            all_theta = [r['theta'] for r in results]
            mean_theta = np.mean(all_theta)
            std_theta = np.std(all_theta) if len(all_theta) > 1 else 1.0
            
            # T-score ni qayta hisoblash
            for result in results:
                result['t_score'] = rasch_model.calculate_standard_score(
                    result['theta'], mean_theta, std_theta
                )
            
            # Statistika
            statistics = {
                'total_students': n_students,
                'total_questions': n_items,
                'avg_percentage': np.mean([r['percentage'] for r in results]),
                'avg_theta': mean_theta,
                'std_theta': std_theta,
                'avg_t_score': np.mean([r['t_score'] for r in results]),
                'max_theta': np.max(all_theta),
                'min_theta': np.min(all_theta),
                'method': 'fallback'
            }
            
            # T-score bo'yicha tartiblash
            results.sort(key=lambda x: x['t_score'], reverse=True)
            
            return results, statistics
        
        # Muvaffaqiyatli fit bo'lgan holat (eRm yoki JMLE)
        theta_estimates = rasch_model.theta_estimates
        beta_estimates = rasch_model.beta_estimates
        
        # O'rtacha va standart tafovutni hisoblash
        mean_theta = np.mean(theta_estimates)
        std_theta = np.std(theta_estimates) if len(theta_estimates) > 1 else 1.0
        
        # Har bir talaba uchun natijalarni tayyorlash
        results = []
        for i in range(n_students):
            correct_count = int(np.sum(response_matrix[i, :]))
            theta = theta_estimates[i]
            
            # T-score hisoblash (rasmda ko'rsatilgan formula bo'yicha)
            t_score = rasch_model.calculate_standard_score(theta, mean_theta, std_theta)
            
            results.append({
                'user_id': user_ids[i],
                'correct': correct_count,
                'total': n_items,
                'percentage': (correct_count / n_items * 100) if n_items > 0 else 0,
                'theta': float(theta),
                'rasch_score': float(theta),
                't_score': t_score,
                'responses': response_matrix[i, :].tolist()
            })
        
        # Umumiy statistika
        statistics = {
            'total_students': n_students,
            'total_questions': n_items,
            'avg_percentage': np.mean([r['percentage'] for r in results]),
            'avg_theta': mean_theta,
            'std_theta': std_theta,
            'avg_t_score': np.mean([r['t_score'] for r in results]),
            'max_theta': float(np.max(theta_estimates)),
            'min_theta': float(np.min(theta_estimates)),
            'item_difficulties': beta_estimates.tolist() if beta_estimates is not None else [],
            'method': 'eRm' if rasch_model.use_erm else 'JMLE'
        }
        
        # T-score bo'yicha tartiblash (yuqoridan pastga)
        results.sort(key=lambda x: x['t_score'], reverse=True)
        
        logger.info(f"✅ Rasch model baholash tugadi: {statistics['method']} usuli")
        
        return results, statistics
        
    except Exception as e:
        logger.error(f"Rasch baholash xatosi: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None
